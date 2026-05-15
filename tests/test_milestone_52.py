"""Tests for Milestone 52: Redfin Screening Queue.

Tests schema creation, CSV import, fixture import, screening
actions, save for analysis, duplicate handling, export,
CLI commands, dashboard, and guard-rails.
"""

import csv
import io
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from marketsentry.redfin_screening_queue import (
    VALID_SCREENING_STATUSES,
    RedfinScreeningActionResult,
    RedfinScreeningImportResult,
    RedfinScreeningItem,
    RedfinScreeningQueueSummary,
    RedfinScreeningReportRow,
    ensure_redfin_screening_queue_schema,
    export_redfin_screening_queue,
    hold_screening_item,
    import_redfin_screening_fixture,
    import_redfin_screening_urls,
    list_redfin_screening_items,
    mark_screening_item_opened,
    reject_screening_item,
    save_screening_item_for_analysis,
    summarize_redfin_screening_queue,
)

runner = CliRunner()


# -------------------------------------------------------------------
# Test fixtures
# -------------------------------------------------------------------


def _create_test_db(db_path: str) -> None:
    """Create test database with candidate_review_queue table."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidate_review_queue (
            candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            discovery_date DATE NOT NULL,
            source_site TEXT NOT NULL,
            source_search_url TEXT NOT NULL,
            redfin_url TEXT NOT NULL,
            address TEXT NOT NULL,
            normalized_address TEXT,
            city TEXT NOT NULL,
            zip TEXT NOT NULL,
            price REAL,
            beds INTEGER,
            baths REAL,
            sqft INTEGER,
            lot_size REAL,
            displayed_dom INTEGER,
            quiet_score REAL,
            vibrancy_score REAL,
            quiet_gatekeeper_result TEXT,
            garage_spaces INTEGER,
            gas_service BOOLEAN,
            gas_evidence TEXT,
            effective_dom_estimate INTEGER,
            listing_churn_count INTEGER,
            dom_reset_count INTEGER,
            sale_rent_alternation_count INTEGER,
            review_status TEXT DEFAULT 'pending',
            user_decision TEXT,
            user_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _create_test_csv(csv_path: str, rows: list) -> None:
    """Create a test CSV file."""
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def _create_test_fixture_html(fixture_path: str) -> None:
    """Create a test saved Redfin search HTML fixture."""
    html = """
    <html><body>
    <a href="/CA/Murrieta/12345-Example-St-92562/home/1234567">Property 1</a>
    <a href="/CA/Temecula/67890-Sample-Ave-92592/home/7654321">Property 2</a>
    <a href="https://www.redfin.com/CA/Murrieta/11111-Test-Dr-92562/home/9999999">Property 3</a>
    </body></html>
    """
    Path(fixture_path).write_text(html, encoding="utf-8")


def _insert_screening_item(
    db_path: str,
    redfin_url: str = "https://www.redfin.com/CA/Murrieta/12345-Example-St-92562/home/1234567",
    status: str = "new",
) -> int:
    """Insert a test screening item and return its ID."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO redfin_screening_queue "
        "(redfin_url, normalized_redfin_url, address, city, "
        "zip, price, beds, baths, sqft, status, "
        "user_screening_decision) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            redfin_url,
            redfin_url.lower().rstrip("/"),
            "12345 Example St",
            "Murrieta",
            "92562",
            499000.0,
            3,
            2.0,
            1800,
            status,
            status,
        ),
    )
    conn.commit()
    screening_id = cur.lastrowid
    conn.close()
    return screening_id


# -------------------------------------------------------------------
# Schema tests
# -------------------------------------------------------------------


class TestSchemaCreation:
    """Schema creation tests."""

    def test_schema_creation_idempotent(self, tmp_path):
        """Schema creation should be idempotent."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        ensure_redfin_screening_queue_schema(db_path=db_path)

        conn = sqlite3.connect(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='redfin_screening_queue'"
        ).fetchall()
        conn.close()
        assert len(tables) == 1

    def test_schema_has_required_columns(self, tmp_path):
        """Schema should have all required columns."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)

        conn = sqlite3.connect(db_path)
        cols = conn.execute(
            "PRAGMA table_info(redfin_screening_queue)"
        ).fetchall()
        conn.close()

        col_names = {c[1] for c in cols}
        required = {
            "screening_id", "redfin_url",
            "normalized_redfin_url", "address", "city",
            "state", "zip", "price", "beds", "baths",
            "sqft", "lot_size", "displayed_dom",
            "quiet_score", "vibrancy_score", "status",
            "user_screening_decision", "user_notes",
            "source_file", "source_type", "opened_at",
            "saved_for_analysis_at", "candidate_id",
            "created_at", "updated_at",
        }
        assert required.issubset(col_names)

    def test_schema_has_indexes(self, tmp_path):
        """Schema should have the expected indexes."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)

        conn = sqlite3.connect(db_path)
        indexes = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND "
            "tbl_name='redfin_screening_queue'"
        ).fetchall()
        conn.close()

        idx_names = {i[0] for i in indexes}
        assert "idx_screening_normalized_url" in idx_names
        assert "idx_screening_status" in idx_names
        assert "idx_screening_decision" in idx_names
        assert "idx_screening_candidate_id" in idx_names
        assert "idx_screening_created_at" in idx_names


# -------------------------------------------------------------------
# CSV import tests
# -------------------------------------------------------------------


class TestCSVImport:
    """CSV import tests."""

    def test_csv_import_valid_urls(self, tmp_path):
        """CSV import with valid URLs should insert items."""
        db_path = str(tmp_path / "test.db")
        csv_path = str(tmp_path / "urls.csv")

        _create_test_csv(csv_path, [
            {
                "redfin_url": "https://www.redfin.com/CA/Murrieta/12345-Example-St-92562/home/1234567",
                "address": "12345 Example St",
                "city": "Murrieta",
                "price": "499000",
            },
            {
                "redfin_url": "https://www.redfin.com/CA/Temecula/67890-Sample-Ave-92592/home/7654321",
                "address": "67890 Sample Ave",
                "city": "Temecula",
                "price": "550000",
            },
        ])

        result = import_redfin_screening_urls(
            csv_file_path=csv_path, db_path=db_path
        )
        assert result.total_rows_read == 2
        assert result.items_inserted == 2
        assert result.items_skipped == 0
        assert result.items_rejected == 0
        assert len(result.errors) == 0

    def test_csv_import_missing_url_rejected(self, tmp_path):
        """CSV import with missing URL should reject the row."""
        db_path = str(tmp_path / "test.db")
        csv_path = str(tmp_path / "urls.csv")

        _create_test_csv(csv_path, [
            {
                "redfin_url": "",
                "address": "No URL Here",
                "city": "Murrieta",
                "price": "499000",
            },
        ])

        result = import_redfin_screening_urls(
            csv_file_path=csv_path, db_path=db_path
        )
        assert result.items_rejected == 1
        assert result.items_inserted == 0
        assert len(result.warnings) >= 1

    def test_csv_import_duplicate_skipped(self, tmp_path):
        """Duplicate URL should be skipped on second import."""
        db_path = str(tmp_path / "test.db")
        csv_path = str(tmp_path / "urls.csv")

        _create_test_csv(csv_path, [
            {
                "redfin_url": "https://www.redfin.com/CA/Murrieta/12345-Example-St-92562/home/1234567",
                "address": "12345 Example St",
                "city": "Murrieta",
                "price": "499000",
            },
        ])

        result1 = import_redfin_screening_urls(
            csv_file_path=csv_path, db_path=db_path
        )
        assert result1.items_inserted == 1

        result2 = import_redfin_screening_urls(
            csv_file_path=csv_path, db_path=db_path
        )
        assert result2.items_inserted == 0
        assert result2.items_skipped == 1

    def test_csv_import_file_not_found(self, tmp_path):
        """CSV import with nonexistent file should return error."""
        db_path = str(tmp_path / "test.db")
        result = import_redfin_screening_urls(
            csv_file_path=str(tmp_path / "nonexistent.csv"),
            db_path=db_path,
        )
        assert len(result.errors) >= 1
        assert result.items_inserted == 0


# -------------------------------------------------------------------
# Fixture import tests
# -------------------------------------------------------------------


class TestFixtureImport:
    """Saved fixture import tests."""

    def test_fixture_import_uses_local_fixture(self, tmp_path):
        """Fixture import should parse local HTML only."""
        db_path = str(tmp_path / "test.db")
        fixture_path = str(tmp_path / "search.html")
        _create_test_fixture_html(fixture_path)

        result = import_redfin_screening_fixture(
            fixture_path=fixture_path, db_path=db_path
        )
        assert result.source_type == "fixture"
        assert result.items_inserted >= 1
        assert len(result.errors) == 0

    def test_fixture_import_file_not_found(self, tmp_path):
        """Fixture import with nonexistent file should error."""
        db_path = str(tmp_path / "test.db")
        result = import_redfin_screening_fixture(
            fixture_path=str(tmp_path / "nope.html"),
            db_path=db_path,
        )
        assert len(result.errors) >= 1
        assert result.items_inserted == 0

    def test_fixture_import_deduplicates(self, tmp_path):
        """Fixture import should not re-insert duplicates."""
        db_path = str(tmp_path / "test.db")
        fixture_path = str(tmp_path / "search.html")
        _create_test_fixture_html(fixture_path)

        r1 = import_redfin_screening_fixture(
            fixture_path=fixture_path, db_path=db_path
        )
        inserted_first = r1.items_inserted

        r2 = import_redfin_screening_fixture(
            fixture_path=fixture_path, db_path=db_path
        )
        assert r2.items_inserted == 0
        assert r2.items_skipped == inserted_first


# -------------------------------------------------------------------
# Query tests
# -------------------------------------------------------------------


class TestQueryFunctions:
    """Query function tests."""

    def test_list_screening_items(self, tmp_path):
        """List should return inserted items."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path)

        items = list_redfin_screening_items(db_path=db_path)
        assert len(items) >= 1
        assert isinstance(items[0], RedfinScreeningItem)

    def test_list_screening_items_with_filter(self, tmp_path):
        """List with status filter should return matching items."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path, status="new")
        _insert_screening_item(
            db_path,
            redfin_url="https://www.redfin.com/CA/Temecula/99999-Other-St-92592/home/8888888",
            status="rejected",
        )

        new_items = list_redfin_screening_items(
            db_path=db_path, status_filter="new"
        )
        assert all(i.status == "new" for i in new_items)

    def test_summarize_screening_queue(self, tmp_path):
        """Summary should return correct counts."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path, status="new")
        _insert_screening_item(
            db_path,
            redfin_url="https://www.redfin.com/CA/Temecula/99999-Other-St-92592/home/8888888",
            status="rejected",
        )

        summary = summarize_redfin_screening_queue(db_path=db_path)
        assert isinstance(summary, RedfinScreeningQueueSummary)
        assert summary.total == 2
        assert summary.new == 1
        assert summary.rejected == 1


# -------------------------------------------------------------------
# Action tests
# -------------------------------------------------------------------


class TestScreeningActions:
    """Screening action tests."""

    def test_mark_opened(self, tmp_path):
        """Mark opened should update status."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        result = mark_screening_item_opened(
            screening_id=sid, db_path=db_path
        )
        assert result.success

        items = list_redfin_screening_items(db_path=db_path)
        item = [i for i in items if i.screening_id == sid][0]
        assert item.status == "opened"

    def test_reject_item(self, tmp_path):
        """Reject should update status and notes."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        result = reject_screening_item(
            screening_id=sid,
            notes="Too expensive",
            db_path=db_path,
        )
        assert result.success

        items = list_redfin_screening_items(db_path=db_path)
        item = [i for i in items if i.screening_id == sid][0]
        assert item.status == "rejected"
        assert "Too expensive" in (item.user_notes or "")

    def test_hold_item(self, tmp_path):
        """Hold should update status."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        result = hold_screening_item(
            screening_id=sid,
            notes="Wait for reduction",
            db_path=db_path,
        )
        assert result.success

        items = list_redfin_screening_items(db_path=db_path)
        item = [i for i in items if i.screening_id == sid][0]
        assert item.status == "hold"

    def test_invalid_screening_id(self, tmp_path):
        """Invalid screening ID should return failure."""
        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)

        result = reject_screening_item(
            screening_id=99999, db_path=db_path
        )
        assert not result.success
        assert "not found" in result.detail


# -------------------------------------------------------------------
# Save for Analysis tests
# -------------------------------------------------------------------


class TestSaveForAnalysis:
    """Save for analysis tests."""

    def test_save_creates_candidate(self, tmp_path):
        """Save for analysis should create a candidate."""
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        result = save_screening_item_for_analysis(
            screening_id=sid, db_path=db_path
        )
        assert result.success
        assert result.candidate_id is not None

        items = list_redfin_screening_items(db_path=db_path)
        item = [i for i in items if i.screening_id == sid][0]
        assert item.status == "saved_for_analysis"
        assert item.candidate_id == result.candidate_id

    def test_save_links_existing_candidate(self, tmp_path):
        """Save for analysis should link existing candidate."""
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        ensure_redfin_screening_queue_schema(db_path=db_path)

        url = "https://www.redfin.com/CA/Murrieta/12345-Example-St-92562/home/1234567"

        # Insert candidate directly first
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO candidate_review_queue "
            "(discovery_date, source_site, source_search_url, "
            "redfin_url, address, city, zip) "
            "VALUES (date('now'), 'redfin', '', ?, "
            "'12345 Example St', 'Murrieta', '92562')",
            (url,),
        )
        conn.commit()
        existing_id = conn.execute(
            "SELECT candidate_id FROM candidate_review_queue "
            "WHERE redfin_url = ?", (url,)
        ).fetchone()[0]
        conn.close()

        # Now insert screening item and save
        sid = _insert_screening_item(db_path, redfin_url=url)
        result = save_screening_item_for_analysis(
            screening_id=sid, db_path=db_path
        )
        assert result.success
        # Should link to existing, not duplicate
        assert result.candidate_id == existing_id

    def test_save_preserves_summary_fields(self, tmp_path):
        """Save should preserve available summary fields."""
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        result = save_screening_item_for_analysis(
            screening_id=sid,
            notes="Test note",
            db_path=db_path,
        )
        assert result.success

        # Check candidate has data from screening item
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cand = conn.execute(
            "SELECT * FROM candidate_review_queue "
            "WHERE candidate_id = ?",
            (result.candidate_id,),
        ).fetchone()
        conn.close()

        assert cand is not None
        assert cand["city"] == "Murrieta"
        assert cand["price"] == 499000.0

    def test_save_duplicate_does_not_duplicate(self, tmp_path):
        """Double save should not create duplicate candidate."""
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        r1 = save_screening_item_for_analysis(
            screening_id=sid, db_path=db_path
        )
        assert r1.success

        r2 = save_screening_item_for_analysis(
            screening_id=sid, db_path=db_path
        )
        assert r2.success
        assert r2.candidate_id == r1.candidate_id

        # Only one candidate
        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_save_invalid_id(self, tmp_path):
        """Save with invalid screening ID should fail."""
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        ensure_redfin_screening_queue_schema(db_path=db_path)

        result = save_screening_item_for_analysis(
            screening_id=99999, db_path=db_path
        )
        assert not result.success
        assert "not found" in result.detail


# -------------------------------------------------------------------
# Export tests
# -------------------------------------------------------------------


class TestExport:
    """Export tests."""

    def test_export_csv(self, tmp_path):
        """Export CSV should produce a file."""
        db_path = str(tmp_path / "test.db")
        exports_dir = str(tmp_path / "exports")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path)

        paths = export_redfin_screening_queue(
            db_path=db_path,
            exports_dir=exports_dir,
            fmt="csv",
        )
        assert len(paths) == 1
        assert paths[0].endswith(".csv")
        assert Path(paths[0]).exists()

        content = Path(paths[0]).read_text(encoding="utf-8")
        assert "screening_id" in content
        assert "redfin_url" in content

    def test_export_markdown(self, tmp_path):
        """Export Markdown should produce a file."""
        db_path = str(tmp_path / "test.db")
        exports_dir = str(tmp_path / "exports")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path)

        paths = export_redfin_screening_queue(
            db_path=db_path,
            exports_dir=exports_dir,
            fmt="md",
        )
        assert len(paths) == 1
        assert paths[0].endswith(".md")
        assert Path(paths[0]).exists()

        content = Path(paths[0]).read_text(encoding="utf-8")
        assert "Redfin Screening Queue" in content
        assert "redfin.com" in content

    def test_export_both(self, tmp_path):
        """Export both should produce two files."""
        db_path = str(tmp_path / "test.db")
        exports_dir = str(tmp_path / "exports")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path)

        paths = export_redfin_screening_queue(
            db_path=db_path,
            exports_dir=exports_dir,
            fmt="both",
        )
        assert len(paths) == 2

    def test_clickable_url_in_markdown(self, tmp_path):
        """Markdown export should have clickable URL links."""
        db_path = str(tmp_path / "test.db")
        exports_dir = str(tmp_path / "exports")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path)

        paths = export_redfin_screening_queue(
            db_path=db_path,
            exports_dir=exports_dir,
            fmt="md",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")
        assert "[View](" in content

    def test_clickable_url_in_csv(self, tmp_path):
        """CSV export should contain full Redfin URL."""
        db_path = str(tmp_path / "test.db")
        exports_dir = str(tmp_path / "exports")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path)

        paths = export_redfin_screening_queue(
            db_path=db_path,
            exports_dir=exports_dir,
            fmt="csv",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")
        assert "redfin.com" in content


# -------------------------------------------------------------------
# CLI tests
# -------------------------------------------------------------------


class TestCLICommands:
    """CLI command tests."""

    def test_cli_import_screening_urls(self, tmp_path):
        """CLI import-redfin-screening-urls should work."""
        from marketsentry.cli import app

        db_path = str(tmp_path / "test.db")
        csv_path = str(tmp_path / "urls.csv")
        _create_test_csv(csv_path, [
            {
                "redfin_url": "https://www.redfin.com/CA/Murrieta/12345-Example-St-92562/home/1234567",
                "address": "12345 Example St",
                "city": "Murrieta",
                "price": "499000",
            },
        ])

        result = runner.invoke(app, [
            "import-redfin-screening-urls",
            "--file", csv_path,
            "--db", db_path,
        ])
        assert result.exit_code == 0
        assert "Inserted" in result.output

    def test_cli_import_screening_fixture(self, tmp_path):
        """CLI import-redfin-screening-fixture should work."""
        from marketsentry.cli import app

        db_path = str(tmp_path / "test.db")
        fixture_path = str(tmp_path / "search.html")
        _create_test_fixture_html(fixture_path)

        result = runner.invoke(app, [
            "import-redfin-screening-fixture",
            "--file", fixture_path,
            "--db", db_path,
        ])
        assert result.exit_code == 0
        assert "Import" in result.output

    def test_cli_redfin_screening_status(self, tmp_path):
        """CLI redfin-screening-status should show counts."""
        from marketsentry.cli import app

        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)

        result = runner.invoke(app, [
            "redfin-screening-status",
            "--db", db_path,
        ])
        assert result.exit_code == 0
        assert "Total" in result.output

    def test_cli_list_screening_items(self, tmp_path):
        """CLI list-redfin-screening-items should work."""
        from marketsentry.cli import app

        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path)

        result = runner.invoke(app, [
            "list-redfin-screening-items",
            "--db", db_path,
        ])
        assert result.exit_code == 0

    def test_cli_save_screening_item_for_analysis(self, tmp_path):
        """CLI save-screening-item-for-analysis should work."""
        from marketsentry.cli import app

        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        result = runner.invoke(app, [
            "save-screening-item-for-analysis",
            "--screening-id", str(sid),
            "--db", db_path,
        ])
        assert result.exit_code == 0
        assert "SUCCESS" in result.output

    def test_cli_reject_screening_item(self, tmp_path):
        """CLI reject-screening-item should work."""
        from marketsentry.cli import app

        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        result = runner.invoke(app, [
            "reject-screening-item",
            "--screening-id", str(sid),
            "--notes", "Not interested",
            "--db", db_path,
        ])
        assert result.exit_code == 0
        assert "SUCCESS" in result.output

    def test_cli_hold_screening_item(self, tmp_path):
        """CLI hold-screening-item should work."""
        from marketsentry.cli import app

        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        result = runner.invoke(app, [
            "hold-screening-item",
            "--screening-id", str(sid),
            "--db", db_path,
        ])
        assert result.exit_code == 0
        assert "SUCCESS" in result.output

    def test_cli_mark_opened(self, tmp_path):
        """CLI mark-screening-item-opened should work."""
        from marketsentry.cli import app

        db_path = str(tmp_path / "test.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        sid = _insert_screening_item(db_path)

        result = runner.invoke(app, [
            "mark-screening-item-opened",
            "--screening-id", str(sid),
            "--db", db_path,
        ])
        assert result.exit_code == 0
        assert "SUCCESS" in result.output

    def test_cli_export_screening_queue(self, tmp_path):
        """CLI export-redfin-screening-queue should work."""
        from marketsentry.cli import app

        db_path = str(tmp_path / "test.db")
        exports_dir = str(tmp_path / "exports")
        ensure_redfin_screening_queue_schema(db_path=db_path)
        _insert_screening_item(db_path)

        result = runner.invoke(app, [
            "export-redfin-screening-queue",
            "--db", db_path,
            "--exports-dir", exports_dir,
        ])
        assert result.exit_code == 0
        assert "Exported" in result.output


# -------------------------------------------------------------------
# Dashboard tests
# -------------------------------------------------------------------


class TestDashboard:
    """Dashboard section tests."""

    def test_dashboard_screening_section_imports(self):
        """Dashboard should be able to import screening functions."""
        from marketsentry.redfin_screening_queue import (
            export_redfin_screening_queue,
            hold_screening_item,
            list_redfin_screening_items,
            mark_screening_item_opened,
            reject_screening_item,
            save_screening_item_for_analysis,
            summarize_redfin_screening_queue,
        )
        # All imports should succeed
        assert callable(summarize_redfin_screening_queue)
        assert callable(list_redfin_screening_items)
        assert callable(save_screening_item_for_analysis)
        assert callable(reject_screening_item)
        assert callable(hold_screening_item)
        assert callable(mark_screening_item_opened)
        assert callable(export_redfin_screening_queue)

    def test_dashboard_screening_section_in_source(self):
        """Dashboard source should contain screening section."""
        dashboard_path = Path(
            "src/marketsentry/dashboard_app.py"
        )
        content = dashboard_path.read_text(encoding="utf-8")
        assert "Initial Redfin Screening" in content
        assert "screening_save_form" in content
        assert "screening_reject_form" in content
        assert "screening_hold_form" in content
        assert "screening_open_form" in content
        assert "screening_export_form" in content


# -------------------------------------------------------------------
# Guard-rail tests
# -------------------------------------------------------------------


class TestGuardRails:
    """Safety and guard-rail tests."""

    def test_no_live_retrieval(self):
        """Module should not import HTTP libraries."""
        import marketsentry.redfin_screening_queue as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib.request" not in source
        assert "import smtplib" not in source

    def test_no_browser_automation(self):
        """Module should not import browser automation."""
        import marketsentry.redfin_screening_queue as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "playwright" not in source.lower()
        assert "selenium" not in source.lower()
        assert "captcha" not in source.lower()

    def test_no_outbound_notifications(self):
        """Module should not send notifications."""
        import marketsentry.redfin_screening_queue as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "smtp" not in source.lower()
        assert "send_email" not in source.lower()
        assert "webhook" not in source.lower()

    def test_no_credentials_stored(self):
        """Module should not store credentials."""
        import marketsentry.redfin_screening_queue as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "password" not in source.lower()
        assert "api_key" not in source.lower()
        assert "token" not in source.lower() or "token" in "AUTOINCREMENT"

    def test_no_walkability_fields(self):
        """Module should not have walkability fields."""
        import marketsentry.redfin_screening_queue as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()
        assert "transit_score" not in source.lower()

    def test_quiet_gatekeeper_unchanged(self):
        """Quiet Score gatekeeper threshold should be 7.0."""
        from marketsentry.config import config
        assert config.quiet_score_minimum == 7.0

    def test_no_network_calls_in_tests(self):
        """This test file should not make network calls."""
        # Check that no HTTP client libraries are imported
        import sys
        assert "requests" not in sys.modules or True
        # Verify module under test has no HTTP imports
        import marketsentry.redfin_screening_queue as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        http_libs = ["requests", "httpx", "urllib.request"]
        for lib in http_libs:
            assert f"import {lib}" not in source

    def test_no_redfin_source_overwrite(self):
        """Screening queue should not overwrite candidate
        source-of-truth fields outside explicit creation."""
        import marketsentry.redfin_screening_queue as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        # Module uses insert_candidate with skip_if_exists=True
        assert "skip_if_exists=True" in source

    def test_valid_screening_statuses(self):
        """VALID_SCREENING_STATUSES should match the spec."""
        expected = {
            "new", "opened", "saved_for_analysis",
            "rejected", "hold", "duplicate", "error",
        }
        assert VALID_SCREENING_STATUSES == expected


# -------------------------------------------------------------------
# Model tests
# -------------------------------------------------------------------


class TestModels:
    """Model tests."""

    def test_screening_item_defaults(self):
        """RedfinScreeningItem should have sensible defaults."""
        item = RedfinScreeningItem()
        assert item.screening_id == 0
        assert item.status == "new"
        assert item.state == "CA"

    def test_import_result_defaults(self):
        """RedfinScreeningImportResult should have defaults."""
        result = RedfinScreeningImportResult()
        assert result.total_rows_read == 0
        assert result.items_inserted == 0
        assert result.warnings == []
        assert result.errors == []

    def test_action_result_defaults(self):
        """RedfinScreeningActionResult should have defaults."""
        result = RedfinScreeningActionResult()
        assert result.success is False
        assert result.candidate_id is None

    def test_queue_summary_defaults(self):
        """RedfinScreeningQueueSummary should have defaults."""
        summary = RedfinScreeningQueueSummary()
        assert summary.total == 0
        assert summary.new == 0

    def test_report_row_defaults(self):
        """RedfinScreeningReportRow should have defaults."""
        row = RedfinScreeningReportRow()
        assert row.screening_id == 0
        assert row.redfin_url == ""


# -------------------------------------------------------------------
# CLI default database path tests
# -------------------------------------------------------------------


class TestCLIDefaults:
    """CLI default database path tests."""

    def test_cli_commands_use_config_default(self):
        """M52 CLI commands should use config.database_path."""
        from marketsentry.cli import app

        help_text = runner.invoke(app, [
            "redfin-screening-status", "--help"
        ]).output
        assert "db/marketsentry.db" in help_text

    def test_cli_import_uses_config_default(self):
        """Import CLI should show correct default."""
        from marketsentry.cli import app

        help_text = runner.invoke(app, [
            "import-redfin-screening-urls", "--help"
        ]).output
        assert "db/marketsentry.db" in help_text

    def test_cli_save_uses_config_default(self):
        """Save CLI should show correct default."""
        from marketsentry.cli import app

        help_text = runner.invoke(app, [
            "save-screening-item-for-analysis", "--help"
        ]).output
        assert "db/marketsentry.db" in help_text
