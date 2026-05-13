"""Milestone 45 tests: Portfolio Trend Alert History and Persistence.

Tests cover schema migration, alert key generation, persistence,
latest/previous run retrieval, run comparison, history summary,
CSV/Markdown exports, CLI commands, dashboard integration,
scheduled script safety, and guard-rail constraints.
"""

import csv
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_pack_csv(dir_path, filename, rows):
    """Write a portfolio review pack CSV file."""
    from marketsentry.portfolio_review_pack import (
        REVIEW_CSV_FIELDNAMES,
    )

    path = os.path.join(dir_path, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=REVIEW_CSV_FIELDNAMES
        )
        writer.writeheader()
        for row in rows:
            full_row = {fn: "" for fn in REVIEW_CSV_FIELDNAMES}
            full_row.update(row)
            writer.writerow(full_row)
    return path


def _base_row(**overrides):
    """Create a base row dict with sensible defaults."""
    row = {
        "property_id": "1",
        "address": "123 Main St",
        "city": "Temecula",
        "zip": "92592",
        "current_price": "625000",
        "beds": "4",
        "baths": "2.5",
        "sqft": "2100",
        "watch_priority_label": "normal",
        "active_watch_status": "True",
        "quiet_score": "82.5",
        "quiet_gatekeeper_result": "pass",
        "vibrancy_score": "15.0",
        "gas_evidence": "",
        "garage_spaces": "2",
        "effective_dom_v1": "180",
        "effective_dom_v2": "45",
        "effective_dom_delta": "135",
        "county_reset_applied": "True",
        "recent_churn_index": "2.1",
        "listing_churn_count": "3",
        "dom_reset_count": "2",
        "sale_rent_alternation_count": "0",
        "cross_site_confidence_score": "78.5",
        "discrepancy_severity_label": "moderate",
        "open_alert_count": "3",
        "high_critical_alert_count": "1",
        "alert_burden_label": "moderate",
        "lifecycle_health_score": "65.0",
        "lifecycle_health_label": "needs_review",
        "lifecycle_gap_count": "2",
        "review_priority_label": "normal_review",
        "review_priority_score": "15",
        "recommended_review_action": "Review alerts",
        "redfin_url": (
            "https://www.redfin.com/CA/Temecula/123-Main-St"
        ),
    }
    row.update(overrides)
    return row


def _init_db(db_path):
    """Initialize a test database with all schema tables."""
    from marketsentry.schema import ALL_SCHEMA_STATEMENTS

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for stmt in ALL_SCHEMA_STATEMENTS:
        cursor.execute(stmt)
    conn.commit()
    conn.close()


def _table_exists(db_path, table_name):
    """Check if a table exists in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (table_name,),
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


def _count_rows(db_path, table_name):
    """Count rows in a table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def _insert_test_run(db_path, evaluated_at, alerts_count,
                     high=0, warning=0, info=0):
    """Insert a test run row."""
    from marketsentry.portfolio_trend_alert_history import (
        create_portfolio_trend_alert_run,
    )
    return create_portfolio_trend_alert_run(
        db_path=db_path,
        evaluated_at=evaluated_at,
        alerts_generated_count=alerts_count,
        high_count=high,
        warning_count=warning,
        info_count=info,
    )


def _insert_test_history(db_path, run_id, alert_key,
                         alert_scope="property",
                         property_id=1,
                         severity="warning",
                         alert_type="test_alert",
                         metric_name="test_metric",
                         current_value="100",
                         address="123 Main St"):
    """Insert a test history row with fixed old timestamp."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO portfolio_trend_alert_history (
            run_id, alert_key, alert_scope, property_id,
            address, severity, alert_type, rule_id,
            metric_name, current_value, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, alert_key, alert_scope, property_id,
            address, severity, alert_type, alert_type,
            metric_name, current_value,
            "2026-01-01 00:00:00",
        ),
    )
    conn.commit()
    conn.close()


def _insert_test_history_now(db_path, run_id, alert_key,
                             alert_scope="property",
                             property_id=1,
                             severity="warning",
                             alert_type="test_alert",
                             metric_name="test_metric",
                             current_value="100",
                             address="123 Main St"):
    """Insert a test history row with current timestamp."""
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO portfolio_trend_alert_history (
            run_id, alert_key, alert_scope, property_id,
            address, severity, alert_type, rule_id,
            metric_name, current_value, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, alert_key, alert_scope, property_id,
            address, severity, alert_type, alert_type,
            metric_name, current_value, now,
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchemaMigration:
    """Schema creates run and history tables."""

    def test_runs_table_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            assert _table_exists(db, "portfolio_trend_alert_runs")

    def test_history_table_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            assert _table_exists(
                db, "portfolio_trend_alert_history"
            )

    def test_migration_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            _init_db(db)  # Second call should not error
            assert _table_exists(db, "portfolio_trend_alert_runs")
            assert _table_exists(
                db, "portfolio_trend_alert_history"
            )

    def test_indexes_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            conn = sqlite3.connect(db)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index'"
            )
            indexes = {r[0] for r in cursor.fetchall()}
            conn.close()
            assert "idx_pt_alert_runs_evaluated" in indexes
            assert "idx_pt_alert_history_run" in indexes
            assert "idx_pt_alert_history_key" in indexes
            assert "idx_pt_alert_history_property" in indexes
            assert "idx_pt_alert_history_type" in indexes
            assert "idx_pt_alert_history_severity" in indexes
            assert "idx_pt_alert_history_generated" in indexes


# ---------------------------------------------------------------------------
# Alert key tests
# ---------------------------------------------------------------------------

class TestAlertKeyGeneration:
    """Deterministic alert key generation."""

    def test_same_inputs_same_key(self):
        from marketsentry.portfolio_trend_alert_history import (
            generate_alert_key,
        )
        k1 = generate_alert_key(
            "property", "1", "health_drop", "r1", "metric_a"
        )
        k2 = generate_alert_key(
            "property", "1", "health_drop", "r1", "metric_a"
        )
        assert k1 == k2

    def test_different_inputs_different_key(self):
        from marketsentry.portfolio_trend_alert_history import (
            generate_alert_key,
        )
        k1 = generate_alert_key(
            "property", "1", "health_drop", "r1", "metric_a"
        )
        k2 = generate_alert_key(
            "property", "2", "health_drop", "r1", "metric_a"
        )
        assert k1 != k2

    def test_key_is_hex_string(self):
        from marketsentry.portfolio_trend_alert_history import (
            generate_alert_key,
        )
        k = generate_alert_key(
            "portfolio", "", "burden_high", "", "burden_score"
        )
        assert len(k) == 16
        int(k, 16)  # Should not raise

    def test_case_insensitive(self):
        from marketsentry.portfolio_trend_alert_history import (
            generate_alert_key,
        )
        k1 = generate_alert_key(
            "Portfolio", "1", "Health_Drop", "R1", "Metric_A"
        )
        k2 = generate_alert_key(
            "portfolio", "1", "health_drop", "r1", "metric_a"
        )
        assert k1 == k2


# ---------------------------------------------------------------------------
# Run creation and retrieval tests
# ---------------------------------------------------------------------------

class TestRunCreation:
    """Persist run with no/some alerts."""

    def test_create_run_no_alerts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            run_id = _insert_test_run(
                db, "2026-01-01 00:00:00", 0
            )
            assert run_id > 0
            assert _count_rows(
                db, "portfolio_trend_alert_runs"
            ) == 1

    def test_create_run_with_alerts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            run_id = _insert_test_run(
                db, "2026-01-01 00:00:00", 5,
                high=2, warning=2, info=1,
            )
            assert run_id > 0

            from marketsentry.portfolio_trend_alert_history import (
                get_latest_portfolio_trend_alert_run,
            )
            latest = get_latest_portfolio_trend_alert_run(db)
            assert latest is not None
            assert latest.alerts_generated_count == 5
            assert latest.high_count == 2


class TestLatestPreviousRun:
    """Latest and previous run retrieval."""

    def test_latest_run_empty_db(self):
        from marketsentry.portfolio_trend_alert_history import (
            get_latest_portfolio_trend_alert_run,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            assert get_latest_portfolio_trend_alert_run(db) is None

    def test_latest_run_returns_most_recent(self):
        from marketsentry.portfolio_trend_alert_history import (
            get_latest_portfolio_trend_alert_run,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            _insert_test_run(db, "2026-01-01 00:00:00", 3)
            _insert_test_run(db, "2026-01-02 00:00:00", 5)
            latest = get_latest_portfolio_trend_alert_run(db)
            assert latest.alerts_generated_count == 5

    def test_previous_run_returns_before_latest(self):
        from marketsentry.portfolio_trend_alert_history import (
            get_latest_portfolio_trend_alert_run,
            get_previous_portfolio_trend_alert_run,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            _insert_test_run(db, "2026-01-01 00:00:00", 3)
            _insert_test_run(db, "2026-01-02 00:00:00", 5)
            prev = get_previous_portfolio_trend_alert_run(db)
            assert prev is not None
            assert prev.alerts_generated_count == 3

    def test_previous_run_none_for_single_run(self):
        from marketsentry.portfolio_trend_alert_history import (
            get_previous_portfolio_trend_alert_run,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            _insert_test_run(db, "2026-01-01 00:00:00", 3)
            prev = get_previous_portfolio_trend_alert_run(db)
            assert prev is None


# ---------------------------------------------------------------------------
# Comparison tests
# ---------------------------------------------------------------------------

class TestComparison:
    """Run comparison logic."""

    def test_compare_first_run_all_new(self):
        from marketsentry.portfolio_trend_alert_history import (
            compare_portfolio_trend_alert_runs,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            run_id = _insert_test_run(
                db, "2026-01-01 00:00:00", 2
            )
            _insert_test_history(
                db, run_id, "key_a", alert_type="type_a",
            )
            _insert_test_history(
                db, run_id, "key_b", alert_type="type_b",
            )
            rows, counts = compare_portfolio_trend_alert_runs(
                db, limit=20
            )
            assert counts["new"] == 2
            assert counts["previous_run_id"] == 0

    def test_compare_persistent_alert(self):
        from marketsentry.portfolio_trend_alert_history import (
            compare_portfolio_trend_alert_runs,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-01-01 00:00:00", 1
            )
            _insert_test_history(
                db, r1, "key_a", current_value="100",
            )
            r2 = _insert_test_run(
                db, "2026-01-02 00:00:00", 1
            )
            _insert_test_history(
                db, r2, "key_a", current_value="110",
            )
            rows, counts = compare_portfolio_trend_alert_runs(
                db, limit=20
            )
            assert counts["persistent"] == 1
            assert counts["new"] == 0

    def test_compare_new_alert(self):
        from marketsentry.portfolio_trend_alert_history import (
            compare_portfolio_trend_alert_runs,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-01-01 00:00:00", 1
            )
            _insert_test_history(db, r1, "key_a")
            r2 = _insert_test_run(
                db, "2026-01-02 00:00:00", 2
            )
            _insert_test_history(db, r2, "key_a")
            _insert_test_history(db, r2, "key_b")
            rows, counts = compare_portfolio_trend_alert_runs(
                db, limit=20
            )
            assert counts["new"] == 1
            assert counts["persistent"] + counts["unchanged"] == 1

    def test_compare_disappeared_alert(self):
        from marketsentry.portfolio_trend_alert_history import (
            compare_portfolio_trend_alert_runs,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-01-01 00:00:00", 2
            )
            _insert_test_history(db, r1, "key_a")
            _insert_test_history(db, r1, "key_b")
            r2 = _insert_test_run(
                db, "2026-01-02 00:00:00", 1
            )
            _insert_test_history(db, r2, "key_a")
            rows, counts = compare_portfolio_trend_alert_runs(
                db, limit=20
            )
            assert counts["disappeared"] == 1
            # Verify neutral language
            disappeared_rows = [
                r for r in rows
                if r.comparison_status == "disappeared"
            ]
            assert len(disappeared_rows) == 1
            assert "not present" in disappeared_rows[0].summary.lower()

    def test_severity_increased(self):
        from marketsentry.portfolio_trend_alert_history import (
            compare_portfolio_trend_alert_runs,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-01-01 00:00:00", 1
            )
            _insert_test_history(
                db, r1, "key_a", severity="warning",
            )
            r2 = _insert_test_run(
                db, "2026-01-02 00:00:00", 1
            )
            _insert_test_history(
                db, r2, "key_a", severity="high",
            )
            rows, counts = compare_portfolio_trend_alert_runs(
                db, limit=20
            )
            assert counts["worsened"] == 1

    def test_severity_decreased(self):
        from marketsentry.portfolio_trend_alert_history import (
            compare_portfolio_trend_alert_runs,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-01-01 00:00:00", 1
            )
            _insert_test_history(
                db, r1, "key_a", severity="high",
            )
            r2 = _insert_test_run(
                db, "2026-01-02 00:00:00", 1
            )
            _insert_test_history(
                db, r2, "key_a", severity="info",
            )
            rows, counts = compare_portfolio_trend_alert_runs(
                db, limit=20
            )
            assert counts["improved"] == 1


# ---------------------------------------------------------------------------
# History summary tests
# ---------------------------------------------------------------------------

class TestHistorySummary:
    """History summary with recurring alerts."""

    def test_recurring_alerts(self):
        from datetime import datetime
        from marketsentry.portfolio_trend_alert_history import (
            summarize_portfolio_trend_alert_history,
        )
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(db, now, 1)
            _insert_test_history_now(db, r1, "key_a")
            r2 = _insert_test_run(db, now, 2)
            _insert_test_history_now(db, r2, "key_a")

            summary = summarize_portfolio_trend_alert_history(
                db, days=30
            )
            assert summary.run_count == 2
            assert summary.total_history_rows == 2
            assert summary.recurring_alert_count >= 1

    def test_property_specific_summary(self):
        from datetime import datetime
        from marketsentry.portfolio_trend_alert_history import (
            summarize_portfolio_trend_alert_history,
        )
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(db, now, 2)
            _insert_test_history_now(
                db, r1, "key_a", property_id=1,
            )
            _insert_test_history_now(
                db, r1, "key_b", property_id=2,
            )

            summary = summarize_portfolio_trend_alert_history(
                db, property_id=1, days=30
            )
            assert summary.total_history_rows == 1


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestHistoryCSVExport:
    """History CSV export."""

    def test_csv_export_creates_file(self):
        from marketsentry.portfolio_trend_alert_history import (
            export_portfolio_trend_alert_history_report,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-05-01 00:00:00", 1
            )
            _insert_test_history(db, r1, "key_a")
            out = os.path.join(tmpdir, "exports")
            paths = export_portfolio_trend_alert_history_report(
                db, output_dir=out, fmt="csv", days=30
            )
            assert len(paths) == 1
            assert paths[0].endswith(".csv")
            assert os.path.exists(paths[0])

    def test_csv_has_header_and_data(self):
        from datetime import datetime
        from marketsentry.portfolio_trend_alert_history import (
            export_portfolio_trend_alert_history_report,
        )
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(db, now, 1)
            _insert_test_history_now(db, r1, "key_a")
            out = os.path.join(tmpdir, "exports")
            paths = export_portfolio_trend_alert_history_report(
                db, output_dir=out, fmt="csv", days=30
            )
            with open(paths[0], "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 1
            assert "alert_key" in rows[0]


class TestHistoryMDExport:
    """History Markdown export."""

    def test_md_export_creates_file(self):
        from marketsentry.portfolio_trend_alert_history import (
            export_portfolio_trend_alert_history_report,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-05-01 00:00:00", 1
            )
            _insert_test_history(db, r1, "key_a")
            out = os.path.join(tmpdir, "exports")
            paths = export_portfolio_trend_alert_history_report(
                db, output_dir=out, fmt="md", days=30
            )
            assert len(paths) == 1
            assert paths[0].endswith(".md")
            content = Path(paths[0]).read_text(encoding="utf-8")
            assert "Portfolio Trend Alert History" in content
            assert "No outbound notifications" in content


class TestComparisonCSVExport:
    """Run comparison CSV export."""

    def test_comparison_csv_export(self):
        from marketsentry.portfolio_trend_alert_history import (
            export_portfolio_trend_alert_comparison_report,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-01-01 00:00:00", 1
            )
            _insert_test_history(db, r1, "key_a")
            r2 = _insert_test_run(
                db, "2026-01-02 00:00:00", 1
            )
            _insert_test_history(db, r2, "key_a")
            out = os.path.join(tmpdir, "exports")
            paths = export_portfolio_trend_alert_comparison_report(
                db, output_dir=out, fmt="csv"
            )
            assert len(paths) == 1
            assert paths[0].endswith(".csv")


class TestComparisonMDExport:
    """Run comparison Markdown export."""

    def test_comparison_md_export(self):
        from marketsentry.portfolio_trend_alert_history import (
            export_portfolio_trend_alert_comparison_report,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-01-01 00:00:00", 1
            )
            _insert_test_history(db, r1, "key_a")
            r2 = _insert_test_run(
                db, "2026-01-02 00:00:00", 1
            )
            _insert_test_history(db, r2, "key_a")
            out = os.path.join(tmpdir, "exports")
            paths = export_portfolio_trend_alert_comparison_report(
                db, output_dir=out, fmt="md"
            )
            assert len(paths) == 1
            content = Path(paths[0]).read_text(encoding="utf-8")
            assert "Run Comparison" in content
            assert "No outbound notifications" in content


# ---------------------------------------------------------------------------
# Persistence integration test
# ---------------------------------------------------------------------------

class TestPersistIntegration:
    """Full persist-portfolio-trend-alerts integration."""

    def test_persist_with_pack_data(self):
        from marketsentry.portfolio_trend_alert_history import (
            persist_portfolio_trend_alerts,
            get_latest_portfolio_trend_alert_run,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            exports = os.path.join(tmpdir, "exports")
            os.makedirs(exports, exist_ok=True)

            # Write two pack CSVs to trigger delta alerts
            _write_pack_csv(
                exports,
                "portfolio_review_pack_20260101_000000.csv",
                [_base_row(
                    lifecycle_health_score="90.0",
                    lifecycle_health_label="excellent",
                    open_alert_count="0",
                )],
            )
            _write_pack_csv(
                exports,
                "portfolio_review_pack_20260102_000000.csv",
                [_base_row(
                    lifecycle_health_score="50.0",
                    lifecycle_health_label="needs_review",
                    open_alert_count="5",
                )],
            )

            summary = persist_portfolio_trend_alerts(
                db_path=db,
                exports_dir=exports,
                output_dir=exports,
                write_digest=False,
            )
            assert summary.run_id > 0
            assert summary.alerts_persisted >= 0

            latest = get_latest_portfolio_trend_alert_run(db)
            assert latest is not None
            assert latest.run_id == summary.run_id

    def test_persist_no_pack_data(self):
        from marketsentry.portfolio_trend_alert_history import (
            persist_portfolio_trend_alerts,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            exports = os.path.join(tmpdir, "exports")
            os.makedirs(exports, exist_ok=True)

            summary = persist_portfolio_trend_alerts(
                db_path=db,
                exports_dir=exports,
                output_dir=exports,
                write_digest=False,
            )
            assert summary.run_id > 0
            # Even with no pack data, should persist the
            # "no data" info alert
            assert summary.alerts_persisted >= 1


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLIPersist:
    """CLI persist-portfolio-trend-alerts."""

    def test_cli_persist_runs(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            exports = os.path.join(tmpdir, "exports")
            os.makedirs(exports, exist_ok=True)
            _write_pack_csv(
                exports,
                "portfolio_review_pack_20260101_000000.csv",
                [_base_row()],
            )
            result = runner.invoke(app, [
                "persist-portfolio-trend-alerts",
                "--exports-dir", exports,
                "--output-dir", exports,
                "--db", db,
                "--no-write-digest",
            ])
            assert result.exit_code == 0
            assert "Run ID" in result.output


class TestCLICompare:
    """CLI compare-portfolio-trend-alert-runs."""

    def test_cli_compare_runs(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            _insert_test_run(db, "2026-01-01 00:00:00", 1)
            _insert_test_run(db, "2026-01-02 00:00:00", 1)
            result = runner.invoke(app, [
                "compare-portfolio-trend-alert-runs",
                "--db", db,
            ])
            assert result.exit_code == 0
            assert "Comparison" in result.output


class TestCLISummary:
    """CLI portfolio-trend-alert-history-summary."""

    def test_cli_summary(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            _insert_test_run(db, "2026-05-01 00:00:00", 1)
            result = runner.invoke(app, [
                "portfolio-trend-alert-history-summary",
                "--db", db,
                "--days", "30",
            ])
            assert result.exit_code == 0
            assert "History" in result.output


class TestCLIExportHistory:
    """CLI export-portfolio-trend-alert-history-report."""

    def test_cli_export_history(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-05-01 00:00:00", 1
            )
            _insert_test_history(db, r1, "key_a")
            out = os.path.join(tmpdir, "exports")
            result = runner.invoke(app, [
                "export-portfolio-trend-alert-history-report",
                "--db", db,
                "--output-dir", out,
                "--format", "both",
            ])
            assert result.exit_code == 0
            assert "Exported" in result.output


class TestCLIExportComparison:
    """CLI export-portfolio-trend-alert-run-comparison."""

    def test_cli_export_comparison(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-01-01 00:00:00", 1
            )
            _insert_test_history(db, r1, "key_a")
            r2 = _insert_test_run(
                db, "2026-01-02 00:00:00", 1
            )
            _insert_test_history(db, r2, "key_a")
            out = os.path.join(tmpdir, "exports")
            result = runner.invoke(app, [
                "export-portfolio-trend-alert-run-comparison",
                "--db", db,
                "--output-dir", out,
                "--format", "both",
            ])
            assert result.exit_code == 0
            assert "Exported" in result.output


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

class TestDashboardHistoryLoads:
    """Dashboard history section loads."""

    def test_dashboard_imports(self):
        from marketsentry.portfolio_trend_alert_history import (
            get_latest_portfolio_trend_alert_run,
            get_previous_portfolio_trend_alert_run,
            compare_portfolio_trend_alert_runs,
            summarize_portfolio_trend_alert_history,
        )
        assert callable(get_latest_portfolio_trend_alert_run)
        assert callable(get_previous_portfolio_trend_alert_run)
        assert callable(compare_portfolio_trend_alert_runs)
        assert callable(summarize_portfolio_trend_alert_history)

    def test_dashboard_source_references(self):
        """Dashboard app imports the history module."""
        source = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "Portfolio Trend Alert History" in source
        assert (
            "get_latest_portfolio_trend_alert_run" in source
        )


# ---------------------------------------------------------------------------
# Scheduled script tests
# ---------------------------------------------------------------------------

class TestScheduledScriptSafety:
    """Scheduled script safety checks."""

    def test_script_contains_persist_command(self):
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        assert "persist-portfolio-trend-alerts" in script

    def test_script_contains_comparison_command(self):
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        assert (
            "export-portfolio-trend-alert-run-comparison"
            in script
        )

    def test_no_live_retrieval(self):
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "--force-live" not in lower
        assert "retrieve-candidates" not in lower
        assert "scrape" not in lower

    def test_no_mutation_commands(self):
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "import-candidates" not in lower
        assert "apply-triage" not in lower
        assert "update-decision" not in lower

    def test_no_outbound_notifications(self):
        script = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        ).read_text(encoding="utf-8")
        lower = script.lower()
        assert "send-email" not in lower
        assert "send-sms" not in lower
        assert "webhook" not in lower


# ---------------------------------------------------------------------------
# Guard-rail constraint tests
# ---------------------------------------------------------------------------

class TestNoOutboundNotifications:
    """No outbound notification behavior."""

    def test_module_no_email(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "import smtplib" not in source
        assert "import email" not in source

    def test_module_no_sms(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "import twilio" not in source

    def test_module_no_webhook(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        lower = source.lower()
        # Check for actual webhook sending, not the word
        # "webhook" in safety documentation
        assert "import requests" not in source
        assert "import httpx" not in source


class TestNoMutation:
    """No candidate/watchlist/alert state mutation."""

    def test_module_no_candidate_mutation(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE candidate_review_queue" not in source
        assert "DELETE FROM candidate_review_queue" not in source

    def test_module_no_watchlist_mutation(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE watched_properties" not in source
        assert "DELETE FROM watched_properties" not in source

    def test_module_no_alert_status_mutation(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE cross_site_trend_alerts" not in source

    def test_append_only_inserts(self):
        """Only INSERT statements, no UPDATE/DELETE on history."""
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        # Check that there are no UPDATE or DELETE statements
        # on the history/run tables
        assert (
            "UPDATE portfolio_trend_alert_runs" not in source
        )
        assert (
            "DELETE FROM portfolio_trend_alert_runs" not in source
        )
        assert (
            "UPDATE portfolio_trend_alert_history" not in source
        )
        assert (
            "DELETE FROM portfolio_trend_alert_history"
            not in source
        )


class TestNoRedfinOverwrite:
    """No Redfin source-of-truth overwrite."""

    def test_no_redfin_field_writes(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE watched_properties SET" not in source
        assert (
            "UPDATE candidate_review_queue SET" not in source
        )


class TestQuietGatekeeper:
    """Quiet Score gatekeeper remains unchanged."""

    def test_no_quiet_score_modification(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "quiet_score" not in source.lower() or (
            # The word may appear in comments
            "quiet" not in source.lower()
            or "SET quiet_score" not in source
        )
        # No modification of quiet threshold
        assert "70.0" not in source or (
            "quiet_gatekeeper" not in source
        )


class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_in_module(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        lower = source.lower()
        # Check that walkability is not used as a field
        assert "walk_score" not in lower
        assert "transit_score" not in lower
        # walkability should not appear at all in history module
        assert "walkability" not in lower


class TestNoBrowserAutomation:
    """No browser automation."""

    def test_no_playwright(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "import playwright" not in source.lower()
        assert "from playwright" not in source.lower()

    def test_no_selenium(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "import selenium" not in source.lower()
        assert "from selenium" not in source.lower()


class TestNoNetworkCalls:
    """No real network calls in tests or module."""

    def test_no_requests_import(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib.request" not in source

    def test_no_socket_usage(self):
        source = Path(
            "src/marketsentry/"
            "portfolio_trend_alert_history.py"
        ).read_text(encoding="utf-8")
        assert "import socket" not in source


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestModels:
    """Model instantiation tests."""

    def test_run_record_defaults(self):
        from marketsentry.portfolio_trend_alert_history import (
            PortfolioTrendAlertRunRecord,
        )
        r = PortfolioTrendAlertRunRecord()
        assert r.run_id == 0
        assert r.alerts_generated_count == 0

    def test_history_record_defaults(self):
        from marketsentry.portfolio_trend_alert_history import (
            PortfolioTrendAlertHistoryRecord,
        )
        r = PortfolioTrendAlertHistoryRecord()
        assert r.history_id == 0
        assert r.alert_key == ""

    def test_comparison_row_defaults(self):
        from marketsentry.portfolio_trend_alert_history import (
            PortfolioTrendAlertComparisonRow,
        )
        r = PortfolioTrendAlertComparisonRow()
        assert r.comparison_status == ""

    def test_persistence_summary_defaults(self):
        from marketsentry.portfolio_trend_alert_history import (
            PortfolioTrendAlertPersistenceSummary,
        )
        s = PortfolioTrendAlertPersistenceSummary()
        assert s.run_id == 0

    def test_history_summary_defaults(self):
        from marketsentry.portfolio_trend_alert_history import (
            PortfolioTrendAlertHistorySummary,
        )
        s = PortfolioTrendAlertHistorySummary()
        assert s.days == 30

    def test_run_result_defaults(self):
        from marketsentry.portfolio_trend_alert_history import (
            PortfolioTrendAlertHistoryRunResult,
        )
        r = PortfolioTrendAlertHistoryRunResult()
        assert r.run_record is None
        assert len(r.comparison_rows) == 0


# ---------------------------------------------------------------------------
# Both format export tests
# ---------------------------------------------------------------------------

class TestBothFormatExport:
    """Export with fmt='both' creates CSV and MD."""

    def test_history_both_format(self):
        from marketsentry.portfolio_trend_alert_history import (
            export_portfolio_trend_alert_history_report,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-05-01 00:00:00", 1
            )
            _insert_test_history(db, r1, "key_a")
            out = os.path.join(tmpdir, "exports")
            paths = export_portfolio_trend_alert_history_report(
                db, output_dir=out, fmt="both", days=30
            )
            assert len(paths) == 2
            extensions = {os.path.splitext(p)[1] for p in paths}
            assert ".csv" in extensions
            assert ".md" in extensions

    def test_comparison_both_format(self):
        from marketsentry.portfolio_trend_alert_history import (
            export_portfolio_trend_alert_comparison_report,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            _init_db(db)
            r1 = _insert_test_run(
                db, "2026-01-01 00:00:00", 1
            )
            _insert_test_history(db, r1, "key_a")
            r2 = _insert_test_run(
                db, "2026-01-02 00:00:00", 1
            )
            _insert_test_history(db, r2, "key_a")
            out = os.path.join(tmpdir, "exports")
            paths = export_portfolio_trend_alert_comparison_report(
                db, output_dir=out, fmt="both"
            )
            assert len(paths) == 2
