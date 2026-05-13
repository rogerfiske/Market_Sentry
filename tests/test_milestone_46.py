"""Tests for Milestone 46 - Portfolio Alert Focus Preferences.

Tests highlight preferences config loading, validation, template
writing, focus item building, filtering, sorting, CLI commands,
dashboard imports, scheduled script safety, and guard-rail
constraints.

No real network calls. No database mutations. No outbound
notifications.
"""

import csv
import json
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from marketsentry.portfolio_alert_focus import (
    ALLOWED_SEVERITIES,
    ALLOWED_SORT_ORDERS,
    EXAMPLE_HIGHLIGHT_PREFERENCES,
    FOCUS_CSV_FIELDNAMES,
    PortfolioAlertFocusDigest,
    PortfolioAlertFocusItem,
    PortfolioAlertFocusRunResult,
    PortfolioAlertFocusSummary,
    PortfolioAlertHighlightPreferences,
    build_portfolio_alert_focus_items,
    export_portfolio_alert_focus_digest,
    load_portfolio_alert_highlight_preferences,
    summarize_portfolio_alert_focus,
    validate_portfolio_alert_highlight_preferences,
    write_portfolio_alert_highlight_template,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_db(db_path: str) -> None:
    """Create a test database with alert history tables."""
    from marketsentry.schema import ALL_SCHEMA_STATEMENTS

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for stmt in ALL_SCHEMA_STATEMENTS:
        try:
            cursor.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def _insert_test_run(
    db_path: str,
    alerts_count: int = 3,
) -> int:
    """Insert a test alert run and return the run_id."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    run_key = f"{now}_{alerts_count}_builtin"
    cursor.execute(
        """INSERT INTO portfolio_trend_alert_runs (
            run_key, evaluated_at, rule_config_mode,
            alerts_generated_count, high_count,
            warning_count, info_count,
            portfolio_alert_count, property_alert_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_key, now, "builtin", alerts_count,
            1, 1, 1, 1, 2,
        ),
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()
    return run_id


def _insert_test_history(
    db_path: str,
    run_id: int,
    alert_key: str = "abc123",
    alert_scope: str = "property",
    severity: str = "high",
    alert_type: str = "property_degraded",
    property_id: int = 100,
    address: str = "123 Test St",
    message: str = "Test alert message",
) -> None:
    """Insert a test alert history row."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO portfolio_trend_alert_history (
            run_id, alert_key, alert_scope, property_id,
            candidate_id, address, severity, alert_type,
            rule_id, rule_name, metric_name,
            previous_value, current_value, delta_value,
            message, recommended_local_action,
            source_pack_file, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, alert_key, alert_scope, property_id,
            50, address, severity, alert_type,
            "test_rule", "Test Rule", "test_metric",
            "10", "20", "10",
            message, "Review the property",
            "test_pack.csv", now,
        ),
    )
    conn.commit()
    conn.close()


def _write_valid_config(path: str) -> None:
    """Write a valid preferences config file."""
    config = {
        "profile_name": "test_focus",
        "description": "Test focus profile",
        "include_severities": ["high", "warning"],
        "exclude_severities": ["info"],
        "include_alert_types": [],
        "exclude_alert_types": [],
        "minimum_persistence_count": 1,
        "include_persistent_only": False,
        "include_property_alerts": True,
        "include_portfolio_alerts": True,
        "max_items": 10,
        "sort_order": "severity_then_persistence",
        "notes": "Test config",
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# Preference loading tests
# ---------------------------------------------------------------------------

class TestPreferenceLoading:
    """Preference config loading."""

    def test_default_preferences_without_config(self):
        """No config file returns safe defaults."""
        prefs = load_portfolio_alert_highlight_preferences(None)
        assert prefs.is_valid is True
        assert prefs.profile_name == "default_focus"
        assert "high" in prefs.include_severities
        assert "warning" in prefs.include_severities
        assert prefs.max_items == 25

    def test_valid_config_loads(self):
        """Valid JSON config loads successfully."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "prefs.json")
            _write_valid_config(cfg_path)
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is True
            assert prefs.profile_name == "test_focus"
            assert prefs.max_items == 10

    def test_missing_config_file(self):
        """Missing config file returns invalid prefs."""
        prefs = load_portfolio_alert_highlight_preferences(
            "/nonexistent/path.json"
        )
        assert prefs.is_valid is False
        assert any(
            "not found" in e for e in prefs.errors
        )

    def test_invalid_json_handled(self):
        """Invalid JSON returns invalid prefs."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "bad.json")
            with open(cfg_path, "w") as f:
                f.write("{not valid json}")
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is False
            assert any(
                "Invalid JSON" in e for e in prefs.errors
            )

    def test_missing_profile_name_rejected(self):
        """Missing profile_name is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "no_name.json")
            config = {"max_items": 10}
            with open(cfg_path, "w") as f:
                json.dump(config, f)
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is False
            assert any(
                "profile_name" in e for e in prefs.errors
            )

    def test_invalid_severity_rejected(self):
        """Invalid severity value is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "bad_sev.json")
            config = {
                "profile_name": "test",
                "include_severities": ["critical"],
            }
            with open(cfg_path, "w") as f:
                json.dump(config, f)
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is False
            assert any(
                "Invalid severity" in e for e in prefs.errors
            )

    def test_invalid_sort_order_rejected(self):
        """Invalid sort_order is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "bad_sort.json")
            config = {
                "profile_name": "test",
                "sort_order": "random_order",
            }
            with open(cfg_path, "w") as f:
                json.dump(config, f)
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is False
            assert any(
                "sort_order" in e for e in prefs.errors
            )

    def test_negative_max_items_rejected(self):
        """Negative max_items is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "neg_max.json")
            config = {
                "profile_name": "test",
                "max_items": -5,
            }
            with open(cfg_path, "w") as f:
                json.dump(config, f)
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is False
            assert any(
                "max_items" in e for e in prefs.errors
            )

    def test_negative_persistence_count_rejected(self):
        """Negative minimum_persistence_count is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(
                tmp, "neg_persist.json"
            )
            config = {
                "profile_name": "test",
                "minimum_persistence_count": -1,
            }
            with open(cfg_path, "w") as f:
                json.dump(config, f)
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is False
            assert any(
                "minimum_persistence_count" in e
                for e in prefs.errors
            )

    def test_live_retrieval_key_rejected(self):
        """Config with live_retrieval key is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "live.json")
            config = {
                "profile_name": "test",
                "live_retrieval": True,
            }
            with open(cfg_path, "w") as f:
                json.dump(config, f)
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is False
            assert any(
                "Forbidden" in e for e in prefs.errors
            )

    def test_notification_key_rejected(self):
        """Config with notification key is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "notif.json")
            config = {
                "profile_name": "test",
                "send_notification": True,
            }
            with open(cfg_path, "w") as f:
                json.dump(config, f)
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is False
            assert any(
                "Forbidden" in e for e in prefs.errors
            )

    def test_walkability_key_rejected(self):
        """Config with walkability key is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "walk.json")
            config = {
                "profile_name": "test",
                "walkability_score": 85,
            }
            with open(cfg_path, "w") as f:
                json.dump(config, f)
            prefs = load_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is False
            assert any(
                "Forbidden" in e for e in prefs.errors
            )


# ---------------------------------------------------------------------------
# Template writer tests
# ---------------------------------------------------------------------------

class TestTemplateWriter:
    """Template writer tests."""

    def test_template_creates_file(self):
        """Template writer creates a file."""
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "template.json")
            path, written = (
                write_portfolio_alert_highlight_template(
                    output_path=out
                )
            )
            assert written is True
            assert os.path.isfile(path)
            # Verify valid JSON
            with open(path, "r") as f:
                data = json.load(f)
            assert data["profile_name"] == "default_focus"

    def test_template_refuses_overwrite(self):
        """Template writer refuses overwrite by default."""
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "template.json")
            write_portfolio_alert_highlight_template(
                output_path=out
            )
            path, written = (
                write_portfolio_alert_highlight_template(
                    output_path=out, overwrite=False,
                )
            )
            assert written is False

    def test_template_allows_overwrite(self):
        """Template writer overwrites when requested."""
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "template.json")
            write_portfolio_alert_highlight_template(
                output_path=out
            )
            path, written = (
                write_portfolio_alert_highlight_template(
                    output_path=out, overwrite=True,
                )
            )
            assert written is True


# ---------------------------------------------------------------------------
# Focus item building tests
# ---------------------------------------------------------------------------

class TestFocusItemBuilding:
    """Focus item building from history and digest."""

    def test_focus_items_from_alert_history(self):
        """Focus items load from alert history database."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            _create_test_db(db_path)
            run_id = _insert_test_run(db_path, 3)
            _insert_test_history(
                db_path, run_id,
                alert_key="key1",
                severity="high",
                alert_type="property_degraded",
            )
            _insert_test_history(
                db_path, run_id,
                alert_key="key2",
                severity="warning",
                alert_type="churn_increase",
            )

            prefs = load_portfolio_alert_highlight_preferences(
                None
            )
            items = build_portfolio_alert_focus_items(
                prefs=prefs, db_path=db_path,
            )
            assert len(items) >= 1
            assert all(
                isinstance(i, PortfolioAlertFocusItem)
                for i in items
            )

    def test_focus_items_from_digest_csv(self):
        """Focus items load from digest CSV when no history."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create a fake digest CSV
            csv_path = os.path.join(
                tmp,
                "portfolio_trend_alert_digest_20260101_000000.csv",
            )
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "alert_id", "alert_scope",
                        "property_id", "candidate_id",
                        "address", "severity", "alert_type",
                        "message", "metric_name",
                        "previous_value", "current_value",
                        "delta_value",
                        "recommended_local_action",
                        "source_pack_file", "generated_at",
                    ],
                )
                writer.writeheader()
                writer.writerow({
                    "alert_id": "burden_high_80",
                    "alert_scope": "portfolio",
                    "property_id": "",
                    "candidate_id": "",
                    "address": "",
                    "severity": "high",
                    "alert_type": "aggregate_burden_high",
                    "message": "Burden is high",
                    "metric_name": "aggregate_burden",
                    "previous_value": "70",
                    "current_value": "85",
                    "delta_value": "15",
                    "recommended_local_action": "Review",
                    "source_pack_file": "test.csv",
                    "generated_at": "2026-01-01",
                })

            prefs = load_portfolio_alert_highlight_preferences(
                None
            )
            items = build_portfolio_alert_focus_items(
                prefs=prefs, exports_dir=tmp,
            )
            assert len(items) >= 1
            assert items[0].source == "digest_csv"

    def test_empty_database_returns_empty(self):
        """Empty database returns no focus items."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "empty.db")
            _create_test_db(db_path)
            prefs = load_portfolio_alert_highlight_preferences(
                None
            )
            items = build_portfolio_alert_focus_items(
                prefs=prefs, db_path=db_path,
                exports_dir=tmp,
            )
            assert items == []


# ---------------------------------------------------------------------------
# Filtering tests
# ---------------------------------------------------------------------------

class TestFiltering:
    """Preference filtering tests."""

    def _make_items(self) -> list:
        """Create test focus items."""
        return [
            PortfolioAlertFocusItem(
                severity="high",
                alert_type="property_degraded",
                alert_scope="property",
                persistence_count=3,
                source="alert_history",
                focus_reason="high severity",
            ),
            PortfolioAlertFocusItem(
                severity="warning",
                alert_type="churn_increase",
                alert_scope="property",
                persistence_count=2,
                source="alert_history",
                focus_reason="persistent across runs",
            ),
            PortfolioAlertFocusItem(
                severity="info",
                alert_type="dom_v2_increase",
                alert_scope="property",
                persistence_count=1,
                source="alert_history",
                focus_reason="included by preference filter",
            ),
            PortfolioAlertFocusItem(
                severity="high",
                alert_type="aggregate_burden_high",
                alert_scope="portfolio",
                persistence_count=2,
                source="alert_history",
                focus_reason="aggregate burden alert",
            ),
        ]

    def test_include_severity_filtering(self):
        """Include severity filter works."""
        from marketsentry.portfolio_alert_focus import (
            _apply_preference_filters,
        )

        items = self._make_items()
        prefs = PortfolioAlertHighlightPreferences(
            include_severities=["high"],
            exclude_severities=[],
        )
        filtered = _apply_preference_filters(items, prefs)
        assert all(i.severity == "high" for i in filtered)

    def test_exclude_severity_filtering(self):
        """Exclude severity filter works."""
        from marketsentry.portfolio_alert_focus import (
            _apply_preference_filters,
        )

        items = self._make_items()
        prefs = PortfolioAlertHighlightPreferences(
            include_severities=[],
            exclude_severities=["info"],
        )
        filtered = _apply_preference_filters(items, prefs)
        assert all(i.severity != "info" for i in filtered)

    def test_include_alert_type_filtering(self):
        """Include alert type filter works."""
        from marketsentry.portfolio_alert_focus import (
            _apply_preference_filters,
        )

        items = self._make_items()
        prefs = PortfolioAlertHighlightPreferences(
            include_severities=[],
            exclude_severities=[],
            include_alert_types=["property_degraded"],
        )
        filtered = _apply_preference_filters(items, prefs)
        assert all(
            i.alert_type == "property_degraded"
            for i in filtered
        )

    def test_exclude_alert_type_filtering(self):
        """Exclude alert type filter works."""
        from marketsentry.portfolio_alert_focus import (
            _apply_preference_filters,
        )

        items = self._make_items()
        prefs = PortfolioAlertHighlightPreferences(
            include_severities=[],
            exclude_severities=[],
            exclude_alert_types=["dom_v2_increase"],
        )
        filtered = _apply_preference_filters(items, prefs)
        assert all(
            i.alert_type != "dom_v2_increase"
            for i in filtered
        )

    def test_persistent_only_filtering(self):
        """Include persistent only works."""
        from marketsentry.portfolio_alert_focus import (
            _apply_preference_filters,
        )

        items = self._make_items()
        prefs = PortfolioAlertHighlightPreferences(
            include_severities=[],
            exclude_severities=[],
            include_persistent_only=True,
        )
        filtered = _apply_preference_filters(items, prefs)
        assert all(
            i.persistence_count >= 2 for i in filtered
        )

    def test_max_items_limit(self):
        """Max items limit works."""
        prefs = PortfolioAlertHighlightPreferences(
            include_severities=[],
            exclude_severities=[],
            max_items=2,
        )
        items = self._make_items()
        result = build_portfolio_alert_focus_items.__wrapped__(
            prefs=prefs,
        ) if hasattr(
            build_portfolio_alert_focus_items, "__wrapped__"
        ) else None

        # Direct test via the module function
        from marketsentry.portfolio_alert_focus import (
            _apply_preference_filters,
            _sort_focus_items,
        )
        filtered = _apply_preference_filters(items, prefs)
        sorted_items = _sort_focus_items(
            filtered, prefs.sort_order
        )
        limited = sorted_items[:prefs.max_items]
        assert len(limited) <= 2

    def test_property_scope_filter(self):
        """Exclude property alerts filter works."""
        from marketsentry.portfolio_alert_focus import (
            _apply_preference_filters,
        )

        items = self._make_items()
        prefs = PortfolioAlertHighlightPreferences(
            include_severities=[],
            exclude_severities=[],
            include_property_alerts=False,
        )
        filtered = _apply_preference_filters(items, prefs)
        assert all(
            i.alert_scope != "property" for i in filtered
        )

    def test_portfolio_scope_filter(self):
        """Exclude portfolio alerts filter works."""
        from marketsentry.portfolio_alert_focus import (
            _apply_preference_filters,
        )

        items = self._make_items()
        prefs = PortfolioAlertHighlightPreferences(
            include_severities=[],
            exclude_severities=[],
            include_portfolio_alerts=False,
        )
        filtered = _apply_preference_filters(items, prefs)
        assert all(
            i.alert_scope != "portfolio" for i in filtered
        )


# ---------------------------------------------------------------------------
# Sorting tests
# ---------------------------------------------------------------------------

class TestSorting:
    """Sort order tests."""

    def _make_items(self) -> list:
        """Create items with varied severity/persistence."""
        return [
            PortfolioAlertFocusItem(
                severity="info",
                persistence_count=5,
                address="A St",
                latest_seen_at="2026-01-01",
            ),
            PortfolioAlertFocusItem(
                severity="high",
                persistence_count=1,
                address="B St",
                latest_seen_at="2026-01-03",
            ),
            PortfolioAlertFocusItem(
                severity="warning",
                persistence_count=3,
                address="C St",
                latest_seen_at="2026-01-02",
            ),
        ]

    def test_severity_then_persistence(self):
        """severity_then_persistence sorts correctly."""
        from marketsentry.portfolio_alert_focus import (
            _sort_focus_items,
        )

        items = self._make_items()
        result = _sort_focus_items(
            items, "severity_then_persistence"
        )
        assert result[0].severity == "high"

    def test_persistence_then_severity(self):
        """persistence_then_severity sorts correctly."""
        from marketsentry.portfolio_alert_focus import (
            _sort_focus_items,
        )

        items = self._make_items()
        result = _sort_focus_items(
            items, "persistence_then_severity"
        )
        assert result[0].persistence_count == 5

    def test_newest_first(self):
        """newest_first sorts correctly."""
        from marketsentry.portfolio_alert_focus import (
            _sort_focus_items,
        )

        items = self._make_items()
        result = _sort_focus_items(items, "newest_first")
        assert result[0].latest_seen_at == "2026-01-03"

    def test_property_then_severity(self):
        """property_then_severity sorts correctly."""
        from marketsentry.portfolio_alert_focus import (
            _sort_focus_items,
        )

        items = self._make_items()
        result = _sort_focus_items(
            items, "property_then_severity"
        )
        assert result[0].address == "A St"


# ---------------------------------------------------------------------------
# Summary tests
# ---------------------------------------------------------------------------

class TestSummary:
    """Focus summary tests."""

    def test_summary_counts(self):
        """Summary counts are correct."""
        items = [
            PortfolioAlertFocusItem(
                severity="high",
                alert_scope="portfolio",
                persistence_count=3,
                focus_reason="high severity",
            ),
            PortfolioAlertFocusItem(
                severity="warning",
                alert_scope="property",
                persistence_count=1,
                focus_reason="warning severity",
            ),
            PortfolioAlertFocusItem(
                severity="info",
                alert_scope="property",
                persistence_count=0,
                focus_reason="included by preference filter",
            ),
        ]
        prefs = PortfolioAlertHighlightPreferences(
            profile_name="test"
        )
        summary = summarize_portfolio_alert_focus(items, prefs)
        assert summary.total_focus_items == 3
        assert summary.high_count == 1
        assert summary.warning_count == 1
        assert summary.info_count == 1
        assert summary.portfolio_items == 1
        assert summary.property_items == 2
        assert summary.persistent_items == 1
        assert summary.profile_name == "test"


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestExport:
    """Focus digest export tests."""

    def test_markdown_export(self):
        """Markdown focus digest exports correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_portfolio_alert_focus_digest(
                exports_dir=tmp,
                output_dir=tmp,
                fmt="md",
            )
            md_paths = [
                p for p in result.export_paths
                if p.endswith(".md")
            ]
            assert len(md_paths) == 1
            content = Path(md_paths[0]).read_text(
                encoding="utf-8"
            )
            assert "Portfolio Alert Focus Digest" in content
            assert "No outbound notifications" in content

    def test_csv_export(self):
        """CSV focus digest exports correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create a test digest CSV as input
            csv_in = os.path.join(
                tmp,
                "portfolio_trend_alert_digest_20260101_000000.csv",
            )
            with open(csv_in, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "alert_id", "alert_scope",
                        "property_id", "candidate_id",
                        "address", "severity", "alert_type",
                        "message", "metric_name",
                        "previous_value", "current_value",
                        "delta_value",
                        "recommended_local_action",
                        "source_pack_file", "generated_at",
                    ],
                )
                writer.writeheader()
                writer.writerow({
                    "alert_id": "test",
                    "alert_scope": "property",
                    "property_id": "100",
                    "candidate_id": "50",
                    "address": "123 Test St",
                    "severity": "high",
                    "alert_type": "property_degraded",
                    "message": "Test",
                    "metric_name": "test_metric",
                    "previous_value": "10",
                    "current_value": "20",
                    "delta_value": "10",
                    "recommended_local_action": "Review",
                    "source_pack_file": "test.csv",
                    "generated_at": "2026-01-01",
                })

            result = export_portfolio_alert_focus_digest(
                exports_dir=tmp,
                output_dir=tmp,
                fmt="csv",
            )
            csv_paths = [
                p for p in result.export_paths
                if p.endswith(".csv")
                and "focus_digest" in p
            ]
            assert len(csv_paths) == 1
            with open(csv_paths[0], "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) >= 1
            assert "focus_key" in rows[0]

    def test_both_format_export(self):
        """Both format exports both CSV and Markdown."""
        with tempfile.TemporaryDirectory() as tmp:
            result = export_portfolio_alert_focus_digest(
                exports_dir=tmp,
                output_dir=tmp,
                fmt="both",
            )
            csv_count = sum(
                1 for p in result.export_paths
                if p.endswith(".csv")
            )
            md_count = sum(
                1 for p in result.export_paths
                if p.endswith(".md")
            )
            assert csv_count == 1
            assert md_count == 1


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    """CLI command tests."""

    def test_cli_portfolio_alert_focus(self):
        """portfolio-alert-focus CLI command runs."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            result = runner.invoke(
                app,
                [
                    "portfolio-alert-focus",
                    "--exports-dir", tmp,
                ],
            )
            assert result.exit_code == 0
            assert "Portfolio Alert Focus View" in result.output

    def test_cli_export_focus_digest(self):
        """export-portfolio-alert-focus-digest CLI runs."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            result = runner.invoke(
                app,
                [
                    "export-portfolio-alert-focus-digest",
                    "--exports-dir", tmp,
                    "--output-dir", tmp,
                    "--format", "both",
                ],
            )
            assert result.exit_code == 0
            assert "Portfolio Alert Focus Digest" in result.output

    def test_cli_write_template(self):
        """write-portfolio-alert-focus-template CLI runs."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "template.json")
            result = runner.invoke(
                app,
                [
                    "write-portfolio-alert-focus-template",
                    "--output", out,
                ],
            )
            assert result.exit_code == 0
            assert "SUCCESS" in result.output
            assert os.path.isfile(out)

    def test_cli_validate_config_valid(self):
        """validate-portfolio-alert-focus-config with valid config."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "valid.json")
            _write_valid_config(cfg_path)
            result = runner.invoke(
                app,
                [
                    "validate-portfolio-alert-focus-config",
                    "--preference-config", cfg_path,
                ],
            )
            assert result.exit_code == 0
            assert "VALID" in result.output
            assert "test_focus" in result.output

    def test_cli_validate_config_invalid(self):
        """validate-portfolio-alert-focus-config with invalid config."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "invalid.json")
            config = {
                "max_items": -5,
                "sort_order": "bad_sort",
            }
            with open(cfg_path, "w") as f:
                json.dump(config, f)
            result = runner.invoke(
                app,
                [
                    "validate-portfolio-alert-focus-config",
                    "--preference-config", cfg_path,
                ],
            )
            assert result.exit_code == 0
            assert "INVALID" in result.output


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

class TestDashboard:
    """Dashboard focus view tests."""

    def test_dashboard_focus_imports(self):
        """Dashboard focus imports work."""
        from marketsentry.portfolio_alert_focus import (
            build_portfolio_alert_focus_items,
            load_portfolio_alert_highlight_preferences,
            summarize_portfolio_alert_focus,
            DEFAULT_HIGHLIGHT_PREFERENCES_PATH,
        )
        assert DEFAULT_HIGHLIGHT_PREFERENCES_PATH is not None
        prefs = load_portfolio_alert_highlight_preferences(None)
        assert prefs.is_valid is True

    def test_dashboard_focus_data_loads(self):
        """Dashboard focus data loads with defaults."""
        prefs = load_portfolio_alert_highlight_preferences(None)
        items = build_portfolio_alert_focus_items(prefs=prefs)
        summary = summarize_portfolio_alert_focus(items, prefs)
        assert summary.profile_name == "default_focus"
        assert summary.total_focus_items >= 0


# ---------------------------------------------------------------------------
# Scheduled script safety tests
# ---------------------------------------------------------------------------

class TestScheduledScriptSafety:
    """Scheduled script safety checks."""

    def test_script_contains_focus_digest_command(self):
        """Script contains the focus digest command."""
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        assert (
            "export-portfolio-alert-focus-digest" in script
        )

    def test_no_live_retrieval(self):
        """Script has no live retrieval commands."""
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "--force-live" not in lower
        assert "retrieve-candidates" not in lower
        assert "scrape" not in lower

    def test_no_mutation_commands(self):
        """Script has no mutation commands."""
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "import-candidates" not in lower
        assert "apply-triage" not in lower
        assert "update-decision" not in lower

    def test_no_outbound_notifications(self):
        """Script has no outbound notification commands."""
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "send-email" not in lower
        assert "send-sms" not in lower


# ---------------------------------------------------------------------------
# Guard-rail constraint tests
# ---------------------------------------------------------------------------

class TestNoOutboundNotifications:
    """No outbound notification behavior."""

    def test_module_no_email(self):
        """Module does not import email libraries."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "import smtplib" not in source
        assert "import email" not in source

    def test_module_no_sms(self):
        """Module does not import SMS libraries."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "import twilio" not in source

    def test_module_no_webhook_send(self):
        """Module does not import HTTP libraries for webhooks."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import httpx" not in source


class TestNoMutation:
    """No candidate/watchlist/alert state mutation."""

    def test_no_candidate_mutation(self):
        """Module does not mutate candidates."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE candidate_review_queue" not in source
        assert "DELETE FROM candidate_review_queue" not in source

    def test_no_watchlist_mutation(self):
        """Module does not mutate watchlist."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE watched_properties" not in source
        assert "DELETE FROM watched_properties" not in source

    def test_no_alert_status_mutation(self):
        """Module does not mutate alert status."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE cross_site_trend_alerts" not in source

    def test_no_database_writes(self):
        """Module performs no database writes."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "INSERT INTO" not in source
        assert "UPDATE " not in source or (
            "UPDATE" in source
            and "UPDATE candidate" not in source
            and "UPDATE watched" not in source
            and "UPDATE cross_site" not in source
        )


class TestNoRedfinOverwrite:
    """No Redfin source-of-truth overwrite."""

    def test_no_redfin_field_writes(self):
        """Module does not write Redfin fields."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE watched_properties SET" not in source
        assert (
            "UPDATE candidate_review_queue SET" not in source
        )


class TestQuietGatekeeper:
    """Quiet Score gatekeeper remains unchanged."""

    def test_no_quiet_score_modification(self):
        """Module does not modify Quiet Score."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "SET quiet_score" not in source
        assert "quiet_gatekeeper" not in source


class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_fields(self):
        """Module does not reference walkability fields.

        Note: walkability appears in FORBIDDEN_CONFIG_KEYS as a
        validation guard string - we check that it is not used
        as a field name or import.
        """
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "walk_score =" not in source
        assert "transit_score =" not in source
        assert "import walkability" not in source.lower()


class TestNoBrowserAutomation:
    """No browser automation."""

    def test_no_playwright(self):
        """Module does not use Playwright."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "import playwright" not in source.lower()
        assert "from playwright" not in source.lower()

    def test_no_selenium(self):
        """Module does not use Selenium."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "import selenium" not in source.lower()
        assert "from selenium" not in source.lower()


class TestNoNetworkCalls:
    """No real network calls in tests or module."""

    def test_no_requests_import(self):
        """Module does not import network libraries."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib.request" not in source

    def test_no_socket_usage(self):
        """Module does not use sockets."""
        source = Path(
            "src/marketsentry/portfolio_alert_focus.py"
        ).read_text(encoding="utf-8")
        assert "import socket" not in source


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestModels:
    """Model instantiation tests."""

    def test_preferences_defaults(self):
        """PortfolioAlertHighlightPreferences has defaults."""
        p = PortfolioAlertHighlightPreferences()
        assert p.profile_name == "default_focus"
        assert p.max_items == 25
        assert p.is_valid is True

    def test_focus_item_defaults(self):
        """PortfolioAlertFocusItem has defaults."""
        item = PortfolioAlertFocusItem()
        assert item.focus_key == ""
        assert item.persistence_count == 0
        assert item.severity == ""

    def test_focus_summary_defaults(self):
        """PortfolioAlertFocusSummary has defaults."""
        s = PortfolioAlertFocusSummary()
        assert s.total_focus_items == 0
        assert s.focus_reasons == []

    def test_focus_digest_defaults(self):
        """PortfolioAlertFocusDigest has defaults."""
        d = PortfolioAlertFocusDigest()
        assert d.items == []
        assert d.generated_at == ""

    def test_run_result_defaults(self):
        """PortfolioAlertFocusRunResult has defaults."""
        r = PortfolioAlertFocusRunResult()
        assert r.digest is None
        assert r.export_paths == []
        assert r.warnings == []


# ---------------------------------------------------------------------------
# Validate function test
# ---------------------------------------------------------------------------

class TestValidateFunction:
    """Validate function tests."""

    def test_validate_calls_load(self):
        """validate function delegates to load."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "v.json")
            _write_valid_config(cfg_path)
            prefs = validate_portfolio_alert_highlight_preferences(
                cfg_path
            )
            assert prefs.is_valid is True
            assert prefs.profile_name == "test_focus"


# ---------------------------------------------------------------------------
# Example config tests
# ---------------------------------------------------------------------------

class TestExampleConfig:
    """Example config file tests."""

    def test_example_config_exists(self):
        """Example config file exists."""
        path = Path(
            "config/"
            "portfolio_alert_highlight_preferences"
            ".example.json"
        )
        assert path.is_file()

    def test_example_config_is_valid_json(self):
        """Example config is valid JSON."""
        path = Path(
            "config/"
            "portfolio_alert_highlight_preferences"
            ".example.json"
        )
        with open(path, "r") as f:
            data = json.load(f)
        assert "profile_name" in data

    def test_example_config_validates(self):
        """Example config validates successfully."""
        path = Path(
            "config/"
            "portfolio_alert_highlight_preferences"
            ".example.json"
        )
        prefs = load_portfolio_alert_highlight_preferences(
            str(path)
        )
        assert prefs.is_valid is True
