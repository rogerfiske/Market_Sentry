"""Database initialization and management."""

import sqlite3
from pathlib import Path
from typing import Any, List, Optional

from marketsentry.config import config
from marketsentry.logging_config import logger
from marketsentry.schema import ALL_SCHEMA_STATEMENTS


def get_connection(database_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Get a database connection.

    Args:
        database_path: Path to database file (uses config default if not specified)

    Returns:
        SQLite connection object
    """
    db_path = database_path or config.database_path

    # Ensure database directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name

    return conn


def init_db(database_path: Optional[str] = None) -> None:
    """
    Initialize the database schema.

    Creates all tables and indexes if they don't exist.

    Args:
        database_path: Path to database file (uses config default if not specified)
    """
    db_path = database_path or config.database_path
    logger.info(f"Initializing database at {db_path}")

    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Execute all schema statements
        for statement in ALL_SCHEMA_STATEMENTS:
            cursor.execute(statement)

        conn.commit()
        logger.info("Database schema initialized successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing database: {e}")
        raise

    finally:
        conn.close()


def execute_query(
    query: str, params: Optional[tuple] = None, database_path: Optional[str] = None
) -> List[sqlite3.Row]:
    """
    Execute a SELECT query and return results.

    Args:
        query: SQL query string
        params: Query parameters (optional)
        database_path: Path to database file (uses config default if not specified)

    Returns:
        List of result rows
    """
    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        results = cursor.fetchall()
        return results

    finally:
        conn.close()


def execute_insert(
    query: str, params: Optional[tuple] = None, database_path: Optional[str] = None
) -> int:
    """
    Execute an INSERT query and return the last row ID.

    Args:
        query: SQL INSERT query string
        params: Query parameters (optional)
        database_path: Path to database file (uses config default if not specified)

    Returns:
        Last inserted row ID
    """
    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        conn.commit()
        return cursor.lastrowid

    except Exception as e:
        conn.rollback()
        raise

    finally:
        conn.close()


def execute_update(
    query: str, params: Optional[tuple] = None, database_path: Optional[str] = None
) -> int:
    """
    Execute an UPDATE or DELETE query and return affected row count.

    Args:
        query: SQL UPDATE/DELETE query string
        params: Query parameters (optional)
        database_path: Path to database file (uses config default if not specified)

    Returns:
        Number of affected rows
    """
    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        conn.commit()
        return cursor.rowcount

    except Exception as e:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_table_count(table_name: str, database_path: Optional[str] = None) -> int:
    """
    Get the row count for a table.

    Args:
        table_name: Name of the table
        database_path: Path to database file (uses config default if not specified)

    Returns:
        Number of rows in the table
    """
    query = f"SELECT COUNT(*) as count FROM {table_name}"
    result = execute_query(query, database_path=database_path)
    return result[0]["count"] if result else 0


def table_exists(table_name: str, database_path: Optional[str] = None) -> bool:
    """
    Check if a table exists in the database.

    Args:
        table_name: Name of the table
        database_path: Path to database file (uses config default if not specified)

    Returns:
        True if table exists, False otherwise
    """
    query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
    result = execute_query(query, (table_name,), database_path=database_path)
    return len(result) > 0
