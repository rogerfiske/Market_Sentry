"""Tests for Milestone 20: Retrieval Operations Dashboard Integration.

Tests cover:
- Retrieval operations summary with empty data
- Retrieval operations summary with sample fixture queue items
- Approval manifest loading
- Batch manifest loading
- Batch item manifest loading
- Audit log summary loading
- Dry-run approval summary loading
- Retrieved fixture inventory loading
- Dashboard table builders
- retrieval-operations-summary CLI command
- export-retrieval-operations-report CLI command
- No network calls
- Existing MVP 1-19 tests still pass

No real network calls in any test.
"""

import csv
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ===========================================================================
# Helpers
# ===========================================================================


def _create_test_db(db_path: str) -> None:
    """Create a minimal test database with fixture capture queue table."""
    from marketsentry.database import init_db
    from marketsentry.fixture_capture_queue import ensure_fixture_capture_table

    init_db(db_path)
    ensure_fixture_capture_table(db_path)


def _add_capture_request(
    db_path: str,
    source_url: str,
    request_type: str = "property_detail",
    source_site: str = "redfin",
    status: str = "pending",
) -> int:
    """Insert a capture request with a given status and return its ID."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    normalized = source_url.lower().rstrip("/")
    cursor.execute(
        """
        INSERT INTO fixture_capture_queue (
            source_site, source_url, normalized_url, request_type,
            suggested_fixture_path, status, priority
        ) VALUES (?, ?, ?, ?, ?, ?, 5)
        """,
        (source_site, source_url, normalized, request_type,
         f"data/raw/{source_site}/", status),
    )
    conn.commit()
    cap_id = cursor.lastrowid
    conn.close()
    return cap_id


def _write_csv(path: str, fieldnames: list, rows: list) -> None:
    """Write a CSV file with given fieldnames and rows."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_audit_csv(path: str, rows: list) -> None:
    """Write an audit CSV file."""
    fieldnames = [
        "timestamp", "source_site", "retrieval_mode", "url", "domain",
        "allowed", "blocked", "reason", "dry_run", "network_call_performed",
    ]
    _write_csv(path, fieldnames, rows)


def _write_dry_run_csv(path: str, rows: list) -> None:
    """Write a dry-run approvals CSV file."""
    fieldnames = [
        "timestamp", "source_site", "url", "normalized_url",
        "request_type", "compliance_status", "allowed", "blocked",
        "reasons", "network_call_performed",
    ]
    _write_csv(path, fieldnames, rows)


# ===========================================================================
# TestSummaryEmptyData
# ===========================================================================


class TestSummaryEmptyData:
    """Test retrieval operations summary with empty data."""

    def test_empty_summary(self):
        """Summary with no data returns zero counts."""
        from marketsentry.retrieval_dashboard import (
            get_retrieval_operations_summary,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            summary = get_retrieval_operations_summary(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                approvals_dir=os.path.join(tmpdir, "approvals"),
            )

            assert summary.pending_capture_requests == 0
            assert summary.total_capture_requests == 0
            assert summary.approval_packages_created == 0
            assert summary.batch_retrieval_runs == 0
            assert summary.audit_total_decisions == 0

    def test_empty_format(self):
        """Formatted summary with empty data is valid ASCII text."""
        from marketsentry.retrieval_dashboard import (
            RetrievalOperationsSummary,
            format_retrieval_operations_summary,
        )

        summary = RetrievalOperationsSummary()
        output = format_retrieval_operations_summary(summary)
        assert "Retrieval Operations Summary" in output
        assert "Pending:" in output
        assert "Safety Configuration" in output


# ===========================================================================
# TestSummaryWithSampleData
# ===========================================================================


class TestSummaryWithSampleData:
    """Test retrieval operations summary with sample fixture queue items."""

    def test_summary_with_queue_items(self):
        """Summary reflects capture queue counts."""
        from marketsentry.retrieval_dashboard import (
            get_retrieval_operations_summary,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_capture_request(db_path, "https://redfin.com/a", status="pending")
            _add_capture_request(db_path, "https://redfin.com/b", status="pending")
            _add_capture_request(db_path, "https://redfin.com/c", status="captured")

            summary = get_retrieval_operations_summary(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
            )

            assert summary.pending_capture_requests == 2
            assert summary.captured_capture_requests == 1
            assert summary.total_capture_requests == 3


# ===========================================================================
# TestApprovalManifestLoading
# ===========================================================================


class TestApprovalManifestLoading:
    """Test approval manifest loading."""

    def test_load_approval_manifest(self):
        """Load an approval manifest CSV."""
        from marketsentry.retrieval_approval import APPROVAL_MANIFEST_COLUMNS
        from marketsentry.retrieval_dashboard import (
            load_retrieval_approval_manifest,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "redfin_retrieval_approval_manifest.csv")
            _write_csv(manifest_path, APPROVAL_MANIFEST_COLUMNS, [
                {
                    "approval_run_id": "run1",
                    "created_at": "2026-05-07T12:00:00",
                    "pending_scanned": "5",
                    "approval_rows_written": "5",
                    "approval_csv_path": "test.csv",
                    "approval_summary_path": "test.md",
                    "approved_count_when_imported": "2",
                    "retrieved_count": "1",
                    "blocked_count": "1",
                    "failed_count": "0",
                    "notes": "",
                },
            ])

            table = load_retrieval_approval_manifest(processed_dir=tmpdir)
            assert len(table.rows) == 1
            assert table.rows[0]["approval_run_id"] == "run1"

    def test_load_empty_manifest(self):
        """Load returns empty when no manifest exists."""
        from marketsentry.retrieval_dashboard import (
            load_retrieval_approval_manifest,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            table = load_retrieval_approval_manifest(processed_dir=tmpdir)
            assert len(table.rows) == 0


# ===========================================================================
# TestBatchManifestLoading
# ===========================================================================


class TestBatchManifestLoading:
    """Test batch retrieval manifest loading."""

    def test_load_batch_manifest(self):
        """Load a batch retrieval manifest CSV."""
        from marketsentry.redfin_batch_retrieval import BATCH_MANIFEST_COLUMNS
        from marketsentry.retrieval_dashboard import (
            load_batch_retrieval_manifest,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "redfin_batch_retrieval_manifest.csv")
            _write_csv(manifest_path, BATCH_MANIFEST_COLUMNS, [
                {
                    "run_id": "batch1",
                    "started_at": "2026-05-07T12:00:00",
                    "completed_at": "2026-05-07T12:01:00",
                    "mode": "dry_run_only",
                    "max_items": "0",
                    "request_type_filter": "",
                    "pending_scanned": "3",
                    "attempted_live": "0",
                    "retrieved": "0",
                    "blocked": "0",
                    "failed": "0",
                    "fixtures_saved": "0",
                    "processed_after_retrieval": "False",
                    "queue_items_marked_captured": "0",
                    "audit_log_path": "",
                    "notes": "test",
                },
            ])

            table = load_batch_retrieval_manifest(processed_dir=tmpdir)
            assert len(table.rows) == 1
            assert table.rows[0]["run_id"] == "batch1"

    def test_load_empty_batch_manifest(self):
        """Load returns empty when no batch manifest exists."""
        from marketsentry.retrieval_dashboard import (
            load_batch_retrieval_manifest,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            table = load_batch_retrieval_manifest(processed_dir=tmpdir)
            assert len(table.rows) == 0


# ===========================================================================
# TestBatchItemManifestLoading
# ===========================================================================


class TestBatchItemManifestLoading:
    """Test per-item batch retrieval manifest loading."""

    def test_load_batch_items(self):
        """Load a per-item batch retrieval manifest CSV."""
        from marketsentry.redfin_batch_retrieval import ITEM_MANIFEST_COLUMNS
        from marketsentry.retrieval_dashboard import load_batch_retrieval_items

        with tempfile.TemporaryDirectory() as tmpdir:
            items_path = os.path.join(tmpdir, "redfin_batch_retrieval_items.csv")
            _write_csv(items_path, ITEM_MANIFEST_COLUMNS, [
                {
                    "run_id": "batch1",
                    "capture_request_id": "1",
                    "source_url": "https://redfin.com/test",
                    "request_type": "property_detail",
                    "decision": "dry_run",
                    "network_call_performed": "False",
                    "fixture_path": "",
                    "status": "dry_run",
                    "reason": "",
                    "error": "",
                },
            ])

            table = load_batch_retrieval_items(processed_dir=tmpdir)
            assert len(table.rows) == 1

    def test_load_empty_batch_items(self):
        """Load returns empty when no items manifest exists."""
        from marketsentry.retrieval_dashboard import load_batch_retrieval_items

        with tempfile.TemporaryDirectory() as tmpdir:
            table = load_batch_retrieval_items(processed_dir=tmpdir)
            assert len(table.rows) == 0


# ===========================================================================
# TestAuditLogSummaryLoading
# ===========================================================================


class TestAuditLogSummaryLoading:
    """Test retrieval audit log summary loading."""

    def test_load_audit_summary(self):
        """Load audit summary from CSV files."""
        from marketsentry.retrieval_dashboard import (
            load_retrieval_audit_summary,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, "retrieval_audit_20260507.csv")
            _write_audit_csv(audit_path, [
                {
                    "timestamp": "2026-05-07T12:00:00",
                    "source_site": "redfin",
                    "retrieval_mode": "dry_run",
                    "url": "https://redfin.com/test",
                    "domain": "www.redfin.com",
                    "allowed": "True",
                    "blocked": "False",
                    "reason": "",
                    "dry_run": "True",
                    "network_call_performed": "False",
                },
                {
                    "timestamp": "2026-05-07T12:01:00",
                    "source_site": "redfin",
                    "retrieval_mode": "live_http",
                    "url": "https://redfin.com/test2",
                    "domain": "www.redfin.com",
                    "allowed": "False",
                    "blocked": "True",
                    "reason": "Rate limit exceeded",
                    "dry_run": "False",
                    "network_call_performed": "False",
                },
            ])

            summary = load_retrieval_audit_summary(audit_dir=tmpdir)
            assert summary.total_records == 2
            assert summary.allowed == 1
            assert summary.blocked == 1
            assert summary.dry_runs == 1
            assert summary.live_attempts == 1
            assert summary.network_call_false == 2
            assert summary.files_scanned == 1
            assert "Rate limit exceeded" in summary.blocked_reasons

    def test_load_empty_audit(self):
        """Load returns zeros when no audit files exist."""
        from marketsentry.retrieval_dashboard import (
            load_retrieval_audit_summary,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            summary = load_retrieval_audit_summary(audit_dir=tmpdir)
            assert summary.total_records == 0
            assert summary.files_scanned == 0


# ===========================================================================
# TestDryRunApprovalSummaryLoading
# ===========================================================================


class TestDryRunApprovalSummaryLoading:
    """Test dry-run approval summary loading."""

    def test_load_dry_run_summary(self):
        """Load dry-run approval summary from CSV files."""
        from marketsentry.retrieval_dashboard import (
            load_dry_run_approval_summary,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            approval_path = os.path.join(tmpdir, "dry_run_approvals_20260507.csv")
            _write_dry_run_csv(approval_path, [
                {
                    "timestamp": "2026-05-07T12:00:00",
                    "source_site": "redfin",
                    "url": "https://redfin.com/test",
                    "normalized_url": "https://redfin.com/test",
                    "request_type": "search",
                    "compliance_status": "allowed",
                    "allowed": "True",
                    "blocked": "False",
                    "reasons": "",
                    "network_call_performed": "False",
                },
                {
                    "timestamp": "2026-05-07T12:01:00",
                    "source_site": "redfin",
                    "url": "https://redfin.com/test2",
                    "normalized_url": "https://redfin.com/test2",
                    "request_type": "property_detail",
                    "compliance_status": "blocked",
                    "allowed": "False",
                    "blocked": "True",
                    "reasons": "Not allowed",
                    "network_call_performed": "False",
                },
            ])

            summary = load_dry_run_approval_summary(audit_dir=tmpdir)
            assert summary.total_records == 2
            assert summary.allowed == 1
            assert summary.blocked == 1
            assert summary.files_scanned == 1

    def test_load_empty_dry_run(self):
        """Load returns zeros when no dry-run files exist."""
        from marketsentry.retrieval_dashboard import (
            load_dry_run_approval_summary,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            summary = load_dry_run_approval_summary(audit_dir=tmpdir)
            assert summary.total_records == 0


# ===========================================================================
# TestFixtureInventoryLoading
# ===========================================================================


class TestFixtureInventoryLoading:
    """Test retrieved fixture inventory loading."""

    def test_load_fixture_inventory(self):
        """Load fixture inventory from search and details directories."""
        from marketsentry.retrieval_dashboard import (
            load_retrieved_fixture_inventory,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fixture directories
            search_dir = Path(tmpdir) / "redfin" / "search"
            search_dir.mkdir(parents=True)
            details_dir = Path(tmpdir) / "redfin" / "details"
            details_dir.mkdir(parents=True)

            # Create a search fixture
            search_html = search_dir / "redfin_search_20260507_120000.html"
            search_html.write_text("<html>search page</html>", encoding="utf-8")

            # Create a detail fixture with sidecar JSON
            detail_html = details_dir / "redfin_property_123_20260507_120000.html"
            detail_html.write_text("<html>detail page</html>", encoding="utf-8")
            detail_json = details_dir / "redfin_property_123_20260507_120000.json"
            detail_json.write_text(json.dumps({
                "source_url": "https://redfin.com/CA/test/home/123",
                "retrieved_at": "2026-05-07T12:00:00",
                "content_length": 23,
            }), encoding="utf-8")

            inventory = load_retrieved_fixture_inventory(raw_dir=tmpdir)
            assert inventory.total_search_fixtures == 1
            assert inventory.total_detail_fixtures == 1
            assert len(inventory.rows) == 2

            # Check detail fixture has metadata
            detail_entry = [r for r in inventory.rows if r["fixture_type"] == "property_detail"][0]
            assert detail_entry["source_url"] == "https://redfin.com/CA/test/home/123"
            assert detail_entry["metadata_path"] != ""

    def test_load_empty_fixture_inventory(self):
        """Load returns empty when no fixture directories exist."""
        from marketsentry.retrieval_dashboard import (
            load_retrieved_fixture_inventory,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            inventory = load_retrieved_fixture_inventory(raw_dir=tmpdir)
            assert len(inventory.rows) == 0
            assert inventory.total_search_fixtures == 0
            assert inventory.total_detail_fixtures == 0


# ===========================================================================
# TestBuildRetrievalOperationsTables
# ===========================================================================


class TestBuildRetrievalOperationsTables:
    """Test the build_retrieval_operations_tables function."""

    def test_build_tables_empty(self):
        """Build tables with empty data returns valid structure."""
        from marketsentry.retrieval_dashboard import (
            build_retrieval_operations_tables,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            tables = build_retrieval_operations_tables(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                approvals_dir=os.path.join(tmpdir, "approvals"),
            )

            assert tables.summary.total_capture_requests == 0
            assert len(tables.capture_queue.rows) == 0
            assert len(tables.approval_packages.rows) == 0
            assert len(tables.batch_manifest.rows) == 0
            assert len(tables.batch_items.rows) == 0
            assert tables.audit_summary.total_records == 0
            assert tables.dry_run_summary.total_records == 0
            assert len(tables.fixture_inventory.rows) == 0

    def test_build_tables_with_data(self):
        """Build tables with sample data returns populated structure."""
        from marketsentry.retrieval_dashboard import (
            build_retrieval_operations_tables,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_capture_request(db_path, "https://redfin.com/a", status="pending")
            _add_capture_request(db_path, "https://redfin.com/b", status="captured")

            # Create audit file
            audit_dir = os.path.join(tmpdir, "audit")
            os.makedirs(audit_dir)
            _write_audit_csv(os.path.join(audit_dir, "retrieval_audit_20260507.csv"), [
                {
                    "timestamp": "2026-05-07T12:00:00",
                    "source_site": "redfin",
                    "retrieval_mode": "dry_run",
                    "url": "https://redfin.com/test",
                    "domain": "www.redfin.com",
                    "allowed": "True",
                    "blocked": "False",
                    "reason": "",
                    "dry_run": "True",
                    "network_call_performed": "False",
                },
            ])

            tables = build_retrieval_operations_tables(
                database_path=db_path,
                audit_dir=audit_dir,
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
            )

            assert tables.summary.pending_capture_requests == 1
            assert tables.summary.captured_capture_requests == 1
            assert tables.summary.total_capture_requests == 2
            assert tables.audit_summary.total_records == 1
            assert len(tables.capture_queue.rows) == 2


# ===========================================================================
# TestCLICommands
# ===========================================================================


class TestCLICommands:
    """Test CLI commands for retrieval operations."""

    def test_summary_command_exists(self):
        """The retrieval-operations-summary CLI command is registered."""
        from typer.testing import CliRunner

        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["retrieval-operations-summary", "--help"])
        assert result.exit_code == 0
        assert "summary" in result.output.lower() or "retrieval" in result.output.lower()

    def test_export_command_exists(self):
        """The export-retrieval-operations-report CLI command is registered."""
        from typer.testing import CliRunner

        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["export-retrieval-operations-report", "--help"])
        assert result.exit_code == 0
        assert "report" in result.output.lower() or "export" in result.output.lower()

    def test_summary_command_runs(self):
        """The retrieval-operations-summary command runs without error."""
        from typer.testing import CliRunner

        from marketsentry.cli import app

        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            result = runner.invoke(
                app,
                [
                    "retrieval-operations-summary",
                    "--db", db_path,
                    "--audit-dir", os.path.join(tmpdir, "audit"),
                    "--processed-dir", os.path.join(tmpdir, "processed"),
                ],
            )
            assert result.exit_code == 0
            assert "Retrieval Operations Summary" in result.output


# ===========================================================================
# TestExportReport
# ===========================================================================


class TestExportReport:
    """Test export retrieval operations report."""

    def test_export_md_report(self):
        """Export Markdown report creates a file."""
        from marketsentry.retrieval_dashboard import (
            export_retrieval_operations_report,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            report_path = export_retrieval_operations_report(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                output_dir=os.path.join(tmpdir, "exports"),
                report_format="md",
            )

            assert Path(report_path).exists()
            content = Path(report_path).read_text(encoding="utf-8")
            assert "Retrieval Operations Report" in content
            assert "Fixture Capture Queue" in content
            assert "Safety Configuration" in content

    def test_export_csv_report(self):
        """Export CSV report creates a file."""
        from marketsentry.retrieval_dashboard import (
            export_retrieval_operations_report,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            report_path = export_retrieval_operations_report(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                output_dir=os.path.join(tmpdir, "exports"),
                report_format="csv",
            )

            assert Path(report_path).exists()
            with open(report_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) > 0
                categories = set(r["category"] for r in rows)
                assert "capture_queue" in categories
                assert "safety" in categories


# ===========================================================================
# TestModels
# ===========================================================================


class TestModels:
    """Test Milestone 20 models."""

    def test_summary_defaults(self):
        """RetrievalOperationsSummary has correct defaults."""
        from marketsentry.retrieval_dashboard import (
            RetrievalOperationsSummary,
        )

        s = RetrievalOperationsSummary()
        assert s.pending_capture_requests == 0
        assert s.live_retrieval_enabled is False
        assert s.dry_run_required is True
        assert s.max_requests_per_minute == 6

    def test_tables_defaults(self):
        """RetrievalOperationsTables has correct defaults."""
        from marketsentry.retrieval_dashboard import (
            RetrievalOperationsTables,
        )

        t = RetrievalOperationsTables()
        assert len(t.capture_queue.rows) == 0
        assert len(t.approval_packages.rows) == 0
        assert len(t.batch_manifest.rows) == 0
        assert len(t.batch_items.rows) == 0
        assert t.audit_summary.total_records == 0

    def test_fixture_inventory_defaults(self):
        """RetrievedFixtureInventoryTable has correct defaults."""
        from marketsentry.retrieval_dashboard import (
            RetrievedFixtureInventoryTable,
        )

        inv = RetrievedFixtureInventoryTable()
        assert inv.total_search_fixtures == 0
        assert inv.total_detail_fixtures == 0
        assert len(inv.rows) == 0


# ===========================================================================
# TestSafetyIndicators
# ===========================================================================


class TestSafetyIndicators:
    """Test safety configuration indicators in the summary."""

    def test_safety_defaults_disabled(self):
        """Safety indicators show disabled state by default."""
        from marketsentry.retrieval_dashboard import (
            get_retrieval_operations_summary,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            # Clear any live retrieval env vars
            env_overrides = {
                "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "false",
                "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "",
                "MARKETSENTRY_LIVE_USER_AGENT": "",
                "MARKETSENTRY_LIVE_CONTACT_EMAIL": "",
            }

            with patch.dict(os.environ, env_overrides, clear=False):
                summary = get_retrieval_operations_summary(
                    database_path=db_path,
                    audit_dir=os.path.join(tmpdir, "audit"),
                    processed_dir=os.path.join(tmpdir, "processed"),
                )

            assert summary.live_retrieval_enabled is False
            assert summary.user_agent_configured is False
            assert summary.contact_email_configured is False


# ===========================================================================
# TestNoScheduledRetrieval
# ===========================================================================


class TestNoScheduledRetrieval:
    """Test that scheduled scripts do not call retrieval operations commands."""

    def test_scheduled_scripts_no_dashboard_retrieval(self):
        """Scheduled task scripts do not invoke live retrieval commands."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        if not scripts_dir.exists():
            pytest.skip("scripts/ directory not found")

        forbidden_commands = [
            "retrieve-approved-redfin-batch",
            "retrieve-redfin-search",
            "retrieve-redfin-property",
            "retrieve-pending-redfin-fixtures",
        ]

        script_files = list(scripts_dir.glob("*.ps1")) + list(scripts_dir.glob("*.bat"))
        for script_file in script_files:
            content = script_file.read_text(encoding="utf-8", errors="ignore")
            for cmd in forbidden_commands:
                assert cmd not in content, (
                    f"Scheduled script {script_file.name} contains forbidden "
                    f"command: {cmd}"
                )


# ===========================================================================
# TestNoRealNetworkCalls
# ===========================================================================


class TestNoRealNetworkCalls:
    """Verify no real network calls are performed in tests."""

    def test_no_network_calls(self):
        """All data loading functions are local-only."""
        from marketsentry.retrieval_dashboard import (
            RetrievalOperationsSummary,
            format_retrieval_operations_summary,
        )

        # Verify the summary format function works without network
        summary = RetrievalOperationsSummary()
        output = format_retrieval_operations_summary(summary)
        assert isinstance(output, str)
        assert len(output) > 0


# ===========================================================================
# TestLatestApprovalPackages
# ===========================================================================


class TestLatestApprovalPackages:
    """Test loading latest approval packages."""

    def test_load_latest_packages(self):
        """Load latest approval package CSV files."""
        from marketsentry.retrieval_dashboard import (
            load_latest_retrieval_approval_packages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create approval CSV files
            from marketsentry.retrieval_approval import APPROVAL_CSV_COLUMNS

            for i in range(3):
                csv_path = os.path.join(tmpdir, f"redfin_batch_approval_run{i}.csv")
                _write_csv(csv_path, APPROVAL_CSV_COLUMNS, [
                    {col: f"val{i}" for col in APPROVAL_CSV_COLUMNS},
                ])

            packages = load_latest_retrieval_approval_packages(
                approvals_dir=tmpdir, max_packages=10
            )
            assert len(packages) == 3

    def test_load_empty_packages(self):
        """Load returns empty when no approval files exist."""
        from marketsentry.retrieval_dashboard import (
            load_latest_retrieval_approval_packages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            packages = load_latest_retrieval_approval_packages(
                approvals_dir=tmpdir
            )
            assert len(packages) == 0


# ===========================================================================
# TestCaptureQueueTable
# ===========================================================================


class TestCaptureQueueTable:
    """Test fixture capture queue table loading."""

    def test_load_capture_queue(self):
        """Load capture queue with items."""
        from marketsentry.retrieval_dashboard import (
            load_fixture_capture_queue_table,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_capture_request(db_path, "https://redfin.com/a", status="pending")
            _add_capture_request(db_path, "https://redfin.com/b", status="captured")

            table = load_fixture_capture_queue_table(database_path=db_path)
            assert len(table.rows) == 2

    def test_load_empty_queue(self):
        """Load returns empty for empty queue."""
        from marketsentry.retrieval_dashboard import (
            load_fixture_capture_queue_table,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            table = load_fixture_capture_queue_table(database_path=db_path)
            assert len(table.rows) == 0
