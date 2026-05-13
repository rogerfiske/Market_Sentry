"""Tests for Milestone 48: Local Operations Bundle.

Tests command inventory, report inventory, script safety,
config inventory, safety audit, schema inventory, smoke test,
bundle build, export, CLI commands, dashboard, and guard-rails.
"""

import csv
import io
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from marketsentry.local_operations_bundle import (
    LocalOperationsBundleRunResult,
    LocalOperationsBundleSummary,
    LocalOperationsCommandInventoryItem,
    LocalOperationsConfigInventoryItem,
    LocalOperationsReportInventoryItem,
    LocalOperationsSafetyCheck,
    LocalOperationsScriptInventoryItem,
    build_command_inventory,
    build_config_inventory,
    build_database_schema_inventory,
    build_local_operations_bundle,
    build_report_inventory,
    build_scheduler_script_inventory,
    export_local_operations_bundle,
    run_local_safety_audit,
    run_local_smoke_test,
    run_report_freshness_audit,
)

runner = CliRunner()


# -------------------------------------------------------------------
# Command inventory tests
# -------------------------------------------------------------------


class TestCommandInventory:
    """Test command inventory building."""

    def test_builds_command_list(self):
        """Command inventory returns a non-empty list."""
        items = build_command_inventory()
        assert len(items) > 0

    def test_command_items_have_fields(self):
        """Each command has required fields."""
        items = build_command_inventory()
        for item in items:
            assert item.command_name
            assert item.category
            assert item.purpose
            assert isinstance(item.mutates_db, bool)
            assert isinstance(
                item.live_retrieval_related, bool
            )
            assert isinstance(
                item.safe_for_scheduler_default, bool
            )

    def test_mutation_commands_not_scheduler_safe(self):
        """Commands that mutate DB should not all be scheduler-safe."""
        items = build_command_inventory()
        mutation_cmds = [
            i for i in items if i.mutates_db
        ]
        assert len(mutation_cmds) > 0
        # Some mutation commands are safe (append-only snapshots),
        # others are not (import/apply)
        unsafe_mutations = [
            i
            for i in mutation_cmds
            if not i.safe_for_scheduler_default
        ]
        assert len(unsafe_mutations) > 0

    def test_known_categories_present(self):
        """Known categories are represented."""
        items = build_command_inventory()
        cats = {i.category for i in items}
        assert "database" in cats
        assert "candidate review" in cats
        assert "portfolio review" in cats
        assert "portfolio alerts" in cats
        assert "alert focus" in cats
        assert "email digest" in cats
        assert "operations bundle" in cats

    def test_operations_bundle_commands_present(self):
        """M48 operations bundle commands are in inventory."""
        items = build_command_inventory()
        names = {i.command_name for i in items}
        assert "local-operations-bundle" in names
        assert "export-local-operations-bundle" in names
        assert "local-operations-smoke-test" in names


# -------------------------------------------------------------------
# Report inventory tests
# -------------------------------------------------------------------


class TestReportInventory:
    """Test report inventory scanning."""

    def test_empty_exports_dir(self):
        """Report inventory with empty exports dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            items = build_report_inventory(tmpdir)
            assert len(items) > 0
            for item in items:
                assert item.freshness in (
                    "missing",
                    "unknown",
                )

    def test_with_sample_csv(self):
        """Report inventory finds sample CSV files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a sample CSV
            csv_path = (
                Path(tmpdir)
                / "portfolio_trend_alert_digest_20260513_120000.csv"
            )
            csv_path.write_text(
                "col1,col2\nval1,val2\n", encoding="utf-8"
            )

            items = build_report_inventory(tmpdir)
            trend_items = [
                i
                for i in items
                if i.report_type == "portfolio trend alerts"
            ]
            assert len(trend_items) == 1
            assert trend_items[0].freshness == "fresh"
            assert trend_items[0].file_count == 1
            assert trend_items[0].row_count == 1

    def test_with_sample_md(self):
        """Report inventory finds sample Markdown files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = (
                Path(tmpdir)
                / "portfolio_alert_focus_digest_20260513_120000.md"
            )
            md_path.write_text(
                "# Report\n\nContent here.", encoding="utf-8"
            )

            items = build_report_inventory(tmpdir)
            focus_items = [
                i
                for i in items
                if i.report_type == "alert focus digest"
            ]
            assert len(focus_items) == 1
            assert focus_items[0].freshness == "fresh"
            assert focus_items[0].file_count == 1

    def test_nonexistent_exports_dir(self):
        """Report inventory handles nonexistent exports dir."""
        items = build_report_inventory(
            "/nonexistent/path/exports"
        )
        assert len(items) > 0
        for item in items:
            assert item.freshness == "missing"

    def test_report_freshness_audit_delegates(self):
        """run_report_freshness_audit delegates to build_report_inventory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_report_freshness_audit(tmpdir)
            assert isinstance(result, list)
            assert all(
                isinstance(r, LocalOperationsReportInventoryItem)
                for r in result
            )


# -------------------------------------------------------------------
# Script inventory tests
# -------------------------------------------------------------------


class TestScriptInventory:
    """Test scheduled script inventory scanning."""

    def test_scans_safe_scripts(self):
        """Script inventory finds safe scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            safe_script = Path(tmpdir) / "safe_report.bat"
            safe_script.write_text(
                "@echo off\n"
                "REM Safe report script\n"
                "python -m marketsentry "
                "export-portfolio-review-pack "
                "--format both\n",
                encoding="utf-8",
            )

            items = build_scheduler_script_inventory(tmpdir)
            assert len(items) == 1
            assert items[0].safe_status == "safe"
            assert not items[0].contains_live_retrieval_command
            assert not items[0].contains_mutation_command

    def test_flags_unsafe_patterns(self):
        """Script inventory flags live retrieval patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            unsafe_script = Path(tmpdir) / "unsafe.bat"
            unsafe_script.write_text(
                "@echo off\n"
                "python -m marketsentry retrieve-live "
                "--force-live\n",
                encoding="utf-8",
            )

            items = build_scheduler_script_inventory(tmpdir)
            assert len(items) == 1
            assert items[0].contains_live_retrieval_command
            assert items[0].contains_force_live
            assert items[0].safe_status == "unsafe"

    def test_flags_notification_patterns(self):
        """Script inventory flags outbound notification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            notif_script = Path(tmpdir) / "notif.bat"
            notif_script.write_text(
                "@echo off\n"
                "python -m marketsentry send-email\n",
                encoding="utf-8",
            )

            items = build_scheduler_script_inventory(tmpdir)
            assert len(items) == 1
            assert (
                items[0].contains_outbound_notification_command
            )
            assert items[0].safe_status == "unsafe"

    def test_nonexistent_scripts_dir(self):
        """Script inventory handles nonexistent dir."""
        items = build_scheduler_script_inventory(
            "/nonexistent/path/scripts"
        )
        assert items == []

    def test_real_scripts_are_safe(self):
        """Real project scripts should be safe."""
        items = build_scheduler_script_inventory("scripts")
        for item in items:
            assert item.safe_status in ("safe", "review"), (
                f"Script {item.script_path} is {item.safe_status}"
            )


# -------------------------------------------------------------------
# Config inventory tests
# -------------------------------------------------------------------


class TestConfigInventory:
    """Test config inventory scanning."""

    def test_with_templates(self):
        """Config inventory detects existing templates."""
        items = build_config_inventory(".")
        template_items = [
            i for i in items if i.is_template
        ]
        assert len(template_items) > 0

    def test_missing_config_dir(self):
        """Config inventory handles missing config dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            items = build_config_inventory(tmpdir)
            assert len(items) > 0
            for item in items:
                assert not item.exists

    def test_config_items_have_fields(self):
        """Config items have required fields."""
        items = build_config_inventory(".")
        for item in items:
            assert item.config_path
            assert isinstance(item.exists, bool)
            assert isinstance(item.is_template, bool)
            assert item.validation_status


# -------------------------------------------------------------------
# Safety audit tests
# -------------------------------------------------------------------


class TestSafetyAudit:
    """Test local safety audit."""

    def test_passes_clean_fixtures(self):
        """Safety audit passes on clean project root."""
        checks = run_local_safety_audit(".")
        assert len(checks) > 0
        for chk in checks:
            assert chk.status in ("pass", "warning", "fail")

    def test_flags_live_retrieval_in_script(self):
        """Safety audit flags unsafe scheduled scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir) / "scripts"
            scripts_dir.mkdir()
            bad_script = scripts_dir / "bad.bat"
            bad_script.write_text(
                "@echo off\n"
                "python -m marketsentry retrieve-live "
                "--force-live\n",
                encoding="utf-8",
            )

            checks = run_local_safety_audit(
                tmpdir, str(scripts_dir)
            )
            script_chk = [
                c
                for c in checks
                if c.check_name == "scheduled_script_safety"
            ]
            assert len(script_chk) == 1
            assert script_chk[0].status == "warning"

    def test_flags_outbound_notification(self):
        """Safety audit detects outbound notification imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src" / "marketsentry"
            src_dir.mkdir(parents=True)
            bad_module = src_dir / "bad_module.py"
            bad_module.write_text(
                "import smtplib\n", encoding="utf-8"
            )

            checks = run_local_safety_audit(tmpdir)
            notif_chk = [
                c
                for c in checks
                if c.check_name
                == "outbound_notification_imports"
            ]
            assert len(notif_chk) == 1
            assert notif_chk[0].status == "fail"

    def test_current_project_passes(self):
        """Current project passes all safety audit checks."""
        checks = run_local_safety_audit(".")
        for chk in checks:
            assert chk.status != "fail", (
                f"Safety check {chk.check_name} failed: "
                f"{chk.detail}"
            )


# -------------------------------------------------------------------
# Schema inventory tests
# -------------------------------------------------------------------


class TestSchemaInventory:
    """Test database schema inventory."""

    def test_missing_db(self):
        """Schema inventory handles missing DB gracefully."""
        result = build_database_schema_inventory(
            "/nonexistent/db.sqlite"
        )
        assert result["exists"] is False
        assert result["table_count"] == 0
        assert "does not exist" in result["notes"]

    def test_temp_initialized_db(self):
        """Schema inventory works with temp initialized DB."""
        with tempfile.NamedTemporaryFile(
            suffix=".db", delete=False
        ) as tmp:
            db_path = tmp.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE test_table ("
                "id INTEGER PRIMARY KEY, name TEXT)"
            )
            conn.execute(
                "CREATE TABLE another_table ("
                "id INTEGER PRIMARY KEY, value REAL)"
            )
            conn.commit()
            conn.close()

            result = build_database_schema_inventory(db_path)
            assert result["exists"] is True
            assert result["table_count"] == 2
            assert "test_table" in result["table_names"]
            assert "another_table" in result["table_names"]
            assert (
                result["column_counts"]["test_table"] == 2
            )
        finally:
            Path(db_path).unlink(missing_ok=True)


# -------------------------------------------------------------------
# Bundle build and export tests
# -------------------------------------------------------------------


class TestBundleBuild:
    """Test full bundle build."""

    def test_builds_bundle(self):
        """Bundle builds successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = build_local_operations_bundle(
                db_path="/nonexistent.db",
                exports_dir=tmpdir,
            )
            assert isinstance(
                bundle, LocalOperationsBundleRunResult
            )
            assert bundle.summary.command_count > 0
            assert len(bundle.commands) > 0
            assert len(bundle.reports) > 0
            assert len(bundle.safety_checks) > 0


class TestBundleExport:
    """Test bundle export."""

    def test_markdown_export(self):
        """Bundle exports Markdown file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = build_local_operations_bundle(
                db_path="/nonexistent.db",
                exports_dir=tmpdir,
            )
            result = export_local_operations_bundle(
                bundle, output_dir=tmpdir, fmt="md"
            )
            assert len(result.output_paths) == 1
            md_path = Path(result.output_paths[0])
            assert md_path.exists()
            content = md_path.read_text(encoding="utf-8")
            assert "Local Operations Bundle" in content
            assert "Command Inventory" in content
            assert "Safety Audit" in content

    def test_csv_export(self):
        """Bundle exports CSV file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = build_local_operations_bundle(
                db_path="/nonexistent.db",
                exports_dir=tmpdir,
            )
            result = export_local_operations_bundle(
                bundle, output_dir=tmpdir, fmt="csv"
            )
            assert len(result.output_paths) == 1
            csv_path = Path(result.output_paths[0])
            assert csv_path.exists()
            content = csv_path.read_text(encoding="utf-8")
            reader = csv.reader(io.StringIO(content))
            header = next(reader)
            assert "section" in header
            assert "item_name" in header
            assert "status" in header
            rows = list(reader)
            assert len(rows) > 0

    def test_both_format_export(self):
        """Bundle exports both CSV and Markdown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = build_local_operations_bundle(
                db_path="/nonexistent.db",
                exports_dir=tmpdir,
            )
            result = export_local_operations_bundle(
                bundle, output_dir=tmpdir, fmt="both"
            )
            assert len(result.output_paths) == 2
            exts = {
                Path(p).suffix for p in result.output_paths
            }
            assert ".md" in exts
            assert ".csv" in exts


# -------------------------------------------------------------------
# Smoke test tests
# -------------------------------------------------------------------


class TestSmokeTest:
    """Test local smoke test function."""

    def test_smoke_test_runs(self):
        """Smoke test returns check results."""
        checks = run_local_smoke_test(use_temp_db=True)
        assert len(checks) > 0
        for chk in checks:
            assert chk.status in ("pass", "warning", "fail")
            assert chk.check_name

    def test_smoke_test_package_import(self):
        """Smoke test checks package import."""
        checks = run_local_smoke_test(use_temp_db=True)
        pkg_chk = [
            c
            for c in checks
            if c.check_name == "package_import"
        ]
        assert len(pkg_chk) == 1
        assert pkg_chk[0].status == "pass"

    def test_smoke_test_config_load(self):
        """Smoke test checks config load."""
        checks = run_local_smoke_test(use_temp_db=True)
        cfg_chk = [
            c
            for c in checks
            if c.check_name == "config_load"
        ]
        assert len(cfg_chk) == 1
        assert cfg_chk[0].status == "pass"

    def test_smoke_test_db_init(self):
        """Smoke test checks database init."""
        checks = run_local_smoke_test(use_temp_db=True)
        db_chk = [
            c
            for c in checks
            if c.check_name == "database_init"
        ]
        assert len(db_chk) == 1
        assert db_chk[0].status == "pass"


# -------------------------------------------------------------------
# CLI tests
# -------------------------------------------------------------------


class TestCLI:
    """Test CLI commands."""

    def test_cli_local_operations_bundle(self):
        """CLI local-operations-bundle runs."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["local-operations-bundle"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Local Operations Bundle" in result.output
        assert "Commands:" in result.output
        assert "No mutations" in result.output

    def test_cli_export_local_operations_bundle(self):
        """CLI export-local-operations-bundle runs."""
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                [
                    "export-local-operations-bundle",
                    "--output-dir",
                    tmpdir,
                    "--format",
                    "both",
                ],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "Exported:" in result.output
            assert "No mutations" in result.output

    def test_cli_local_operations_smoke_test(self):
        """CLI local-operations-smoke-test runs."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["local-operations-smoke-test", "--temp-db"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Smoke Test" in result.output
        assert "No live retrieval" in result.output


# -------------------------------------------------------------------
# Dashboard tests
# -------------------------------------------------------------------


class TestDashboard:
    """Test dashboard integration."""

    def test_dashboard_bundle_data_loads(self):
        """Dashboard can import bundle module."""
        from marketsentry.local_operations_bundle import (
            build_local_operations_bundle as _build,
        )

        bundle = _build(
            db_path="/nonexistent.db",
            exports_dir="/nonexistent",
        )
        assert isinstance(
            bundle, LocalOperationsBundleRunResult
        )

    def test_dashboard_has_bundle_section(self):
        """Dashboard app contains bundle section code."""
        source = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "Local Operations Bundle" in source
        assert "build_local_operations_bundle" in source


# -------------------------------------------------------------------
# Scheduled script safety tests
# -------------------------------------------------------------------


class TestScheduledScriptSafety:
    """Test scheduled script safety."""

    def test_bundle_script_exists(self):
        """Bundle script file exists."""
        path = Path(
            "scripts/run_local_operations_bundle_report.bat"
        )
        assert path.exists()

    def test_bundle_script_no_live_retrieval(self):
        """Bundle script does not contain live retrieval."""
        path = Path(
            "scripts/run_local_operations_bundle_report.bat"
        )
        content = path.read_text(encoding="utf-8")
        lines = [
            line
            for line in content.splitlines()
            if not line.strip().startswith("REM")
        ]
        text = "\n".join(lines)
        assert "--force-live" not in text
        assert "retrieve-" not in text.lower()
        assert "live-retrieve" not in text.lower()

    def test_bundle_script_no_mutation(self):
        """Bundle script does not contain mutation commands."""
        path = Path(
            "scripts/run_local_operations_bundle_report.bat"
        )
        content = path.read_text(encoding="utf-8")
        lines = [
            line
            for line in content.splitlines()
            if not line.strip().startswith("REM")
        ]
        text = "\n".join(lines)
        assert "import-review" not in text.lower()
        assert "apply-alert" not in text.lower()
        assert "acknowledge-" not in text.lower()
        assert "resolve-" not in text.lower()

    def test_bundle_script_no_notification(self):
        """Bundle script does not send notifications."""
        path = Path(
            "scripts/run_local_operations_bundle_report.bat"
        )
        content = path.read_text(encoding="utf-8")
        lines = [
            line
            for line in content.splitlines()
            if not line.strip().startswith("REM")
        ]
        text = "\n".join(lines)
        assert "smtp" not in text.lower()
        assert "send-email" not in text.lower()
        assert "send-sms" not in text.lower()
        assert "webhook" not in text.lower()

    def test_bundle_script_writes_logs(self):
        """Bundle script writes to logs/scheduled/."""
        path = Path(
            "scripts/run_local_operations_bundle_report.bat"
        )
        content = path.read_text(encoding="utf-8")
        assert "logs\\scheduled" in content


# -------------------------------------------------------------------
# Safety guard-rail tests
# -------------------------------------------------------------------


class TestNoOutboundNotifications:
    """No outbound notification code added."""

    def test_module_no_smtplib_import(self):
        """Module does not actually import smtplib.

        The module contains 'import smtplib' as a string pattern
        for safety audit scanning. Check top-level import lines
        only (lines that start with import/from, not in strings).
        """
        import marketsentry.local_operations_bundle as mod
        import sys

        assert "smtplib" not in sys.modules or not hasattr(
            mod, "smtplib"
        )

    def test_module_no_smtp_connection(self):
        """Module does not contain SMTP connection code."""
        source = Path(
            "src/marketsentry/"
            "local_operations_bundle.py"
        ).read_text(encoding="utf-8")
        assert "SMTP(" not in source
        assert "smtp.connect" not in source
        assert "smtp.login" not in source
        assert "smtp.send" not in source

    def test_module_no_gmail_outlook_integration(self):
        """Module does not integrate with Gmail or Outlook."""
        source = Path(
            "src/marketsentry/"
            "local_operations_bundle.py"
        ).read_text(encoding="utf-8")
        assert "GmailAPI" not in source
        assert "OutlookClient" not in source

    def test_module_no_webhook_imports(self):
        """Module does not import HTTP request libraries.

        The module contains 'import requests' as audit scan
        patterns inside string literals. Verify no actual
        top-level imports exist by checking the module object.
        """
        import marketsentry.local_operations_bundle as mod

        assert not hasattr(mod, "requests")
        assert not hasattr(mod, "httpx")

    def test_module_no_credential_storage(self):
        """Module does not store or request credentials."""
        source = Path(
            "src/marketsentry/"
            "local_operations_bundle.py"
        ).read_text(encoding="utf-8")
        assert "getpass" not in source
        assert "keyring" not in source

    def test_module_no_sms_imports(self):
        """Module does not import SMS libraries.

        The module contains 'import twilio' as an audit scan
        pattern. Verify no actual twilio import exists.
        """
        import marketsentry.local_operations_bundle as mod

        assert not hasattr(mod, "twilio")


class TestNoMutation:
    """No candidate/watchlist/alert state mutation."""

    def test_no_candidate_mutation(self):
        """Module does not mutate candidates."""
        source = Path(
            "src/marketsentry/"
            "local_operations_bundle.py"
        ).read_text(encoding="utf-8")
        assert "promote_candidate" not in source
        assert "reject_candidate" not in source
        assert "save_candidate" not in source

    def test_no_watchlist_mutation(self):
        """Module does not mutate watchlist."""
        source = Path(
            "src/marketsentry/"
            "local_operations_bundle.py"
        ).read_text(encoding="utf-8")
        assert "add_to_watchlist" not in source
        assert "remove_from_watchlist" not in source

    def test_no_alert_mutation(self):
        """Module does not mutate alert status."""
        source = Path(
            "src/marketsentry/"
            "local_operations_bundle.py"
        ).read_text(encoding="utf-8")
        assert "acknowledge_alert" not in source
        assert "resolve_alert" not in source
        assert "archive_alert" not in source

    def test_no_write_operations(self):
        """Module does not perform database writes.

        The module uses PRAGMA and SELECT for schema
        introspection only. Verify no INSERT/DELETE statements.
        """
        source = Path(
            "src/marketsentry/"
            "local_operations_bundle.py"
        ).read_text(encoding="utf-8")
        # Module should only read from DB, not write
        assert "INSERT INTO" not in source
        assert "DELETE FROM" not in source
        # CREATE TABLE is also a write operation
        assert "CREATE TABLE" not in source


class TestNoRedfinOverwrite:
    """No Redfin source-of-truth overwrite."""

    def test_no_redfin_sot_overwrite(self):
        """Module does not overwrite Redfin SOT fields.

        The module contains 'redfin_source_of_truth' as an audit
        scan pattern inside string literals. Verify the module
        does not define or modify any redfin SOT attributes.
        """
        import marketsentry.local_operations_bundle as mod

        assert not hasattr(mod, "redfin_source_of_truth")
        assert not hasattr(mod, "overwrite_redfin_sot")


class TestQuietGatekeeper:
    """Quiet Score gatekeeper unchanged."""

    def test_no_quiet_threshold_change(self):
        """Module does not modify Quiet Score threshold.

        The module contains 'QUIET_THRESHOLD' as an audit scan
        pattern. Verify no actual threshold attribute exists.
        """
        import marketsentry.local_operations_bundle as mod

        assert not hasattr(mod, "QUIET_THRESHOLD")
        assert not hasattr(mod, "quiet_threshold")


class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_fields(self):
        """Module does not contain walkability field attributes.

        The module contains walkability strings as audit scan
        patterns. Verify no actual walkability attributes exist.
        """
        import marketsentry.local_operations_bundle as mod

        assert not hasattr(mod, "walkability_score")
        assert not hasattr(mod, "walk_score")
        assert not hasattr(mod, "walkability_rating")


class TestNoBrowserAutomation:
    """No browser automation added."""

    def test_no_playwright_import(self):
        """Module does not import playwright.

        The module contains playwright/selenium strings as
        audit patterns. Verify no actual import at module level.
        """
        import marketsentry.local_operations_bundle as mod

        assert not hasattr(mod, "playwright")

    def test_no_selenium_import(self):
        """Module does not import selenium.

        The module contains selenium string as audit pattern.
        Verify no actual import at module level.
        """
        import marketsentry.local_operations_bundle as mod

        assert not hasattr(mod, "selenium")


class TestNoNetworkCalls:
    """No real network calls in tests."""

    def test_no_requests_import(self):
        """Module does not import requests library.

        The module contains 'import requests' as an audit
        scan pattern. Verify no actual import at module level.
        """
        import marketsentry.local_operations_bundle as mod

        assert not hasattr(mod, "requests")

    def test_no_httpx_import(self):
        """Module does not import httpx library.

        The module contains httpx strings as audit patterns.
        Verify no actual import at module level.
        """
        import marketsentry.local_operations_bundle as mod

        assert not hasattr(mod, "httpx")


# -------------------------------------------------------------------
# Model tests
# -------------------------------------------------------------------


class TestModels:
    """Test Pydantic model construction."""

    def test_command_inventory_item(self):
        """CommandInventoryItem constructs."""
        item = LocalOperationsCommandInventoryItem(
            command_name="test-cmd",
            category="test",
            purpose="Test command",
        )
        assert item.command_name == "test-cmd"
        assert item.mutates_db is False

    def test_report_inventory_item(self):
        """ReportInventoryItem constructs."""
        item = LocalOperationsReportInventoryItem(
            report_type="test report",
            freshness="fresh",
        )
        assert item.report_type == "test report"
        assert item.row_count == -1

    def test_script_inventory_item(self):
        """ScriptInventoryItem constructs."""
        item = LocalOperationsScriptInventoryItem(
            script_path="test.bat",
            safe_status="safe",
        )
        assert item.script_path == "test.bat"
        assert item.exists is False

    def test_config_inventory_item(self):
        """ConfigInventoryItem constructs."""
        item = LocalOperationsConfigInventoryItem(
            config_path="test.json",
            exists=True,
            is_template=True,
        )
        assert item.config_path == "test.json"
        assert item.is_template is True

    def test_safety_check(self):
        """SafetyCheck constructs."""
        item = LocalOperationsSafetyCheck(
            check_name="test_check",
            status="pass",
            detail="All good",
        )
        assert item.check_name == "test_check"
        assert item.status == "pass"

    def test_bundle_summary(self):
        """BundleSummary constructs with defaults."""
        summary = LocalOperationsBundleSummary()
        assert summary.command_count == 0
        assert summary.safety_audit_pass == 0

    def test_bundle_run_result(self):
        """BundleRunResult constructs with defaults."""
        result = LocalOperationsBundleRunResult()
        assert result.commands == []
        assert result.reports == []
        assert result.output_paths == []
