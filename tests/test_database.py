"""Tests for database functionality."""

import tempfile
from pathlib import Path

import pytest

from marketsentry.database import (
    execute_query,
    get_connection,
    get_table_count,
    init_db,
    table_exists,
)


@pytest.fixture
def temp_db() -> str:
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


def test_init_db(temp_db: str) -> None:
    """Test database initialization."""
    init_db(temp_db)

    # Verify database file exists
    assert Path(temp_db).exists()

    # Verify tables exist
    assert table_exists("candidate_review_queue", temp_db)
    assert table_exists("watched_properties", temp_db)
    assert table_exists("listing_events", temp_db)


def test_get_connection(temp_db: str) -> None:
    """Test getting a database connection."""
    init_db(temp_db)
    conn = get_connection(temp_db)

    assert conn is not None
    conn.close()


def test_table_exists(temp_db: str) -> None:
    """Test table existence check."""
    init_db(temp_db)

    assert table_exists("candidate_review_queue", temp_db)
    assert not table_exists("nonexistent_table", temp_db)


def test_get_table_count_empty(temp_db: str) -> None:
    """Test getting count from empty table."""
    init_db(temp_db)

    count = get_table_count("candidate_review_queue", temp_db)

    assert count == 0


def test_execute_query(temp_db: str) -> None:
    """Test executing a query."""
    init_db(temp_db)

    results = execute_query(
        "SELECT name FROM sqlite_master WHERE type='table'",
        database_path=temp_db,
    )

    assert len(results) > 0


def test_init_db_idempotent(temp_db: str) -> None:
    """Test that init_db can be run multiple times."""
    init_db(temp_db)
    init_db(temp_db)  # Should not raise error

    assert table_exists("candidate_review_queue", temp_db)


def test_all_tables_created(temp_db: str) -> None:
    """Test that all expected tables are created."""
    init_db(temp_db)

    expected_tables = [
        "candidate_review_queue",
        "watched_properties",
        "property_observation_snapshots",
        "listing_events",
        "source_pages",
        "user_review_actions",
    ]

    for table in expected_tables:
        assert table_exists(table, temp_db), f"Table {table} not created"
