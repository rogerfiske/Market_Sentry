"""Database initialization and management."""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from marketsentry.config import config
from marketsentry.logging_config import logger
from marketsentry.models import CandidateProperty, WatchedProperty
from marketsentry.normalization import normalize_address
from marketsentry.schema import ALL_SCHEMA_STATEMENTS, MIGRATE_PROPERTY_OBSERVATION_SNAPSHOTS_V2


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


def column_exists(
    table_name: str, column_name: str, database_path: Optional[str] = None
) -> bool:
    """
    Check if a column exists in a table.

    Args:
        table_name: Name of the table
        column_name: Name of the column
        database_path: Path to database file

    Returns:
        True if column exists, False otherwise
    """
    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return column_name in columns
    finally:
        conn.close()


def migrate_schema(database_path: Optional[str] = None) -> None:
    """
    Apply schema migrations to existing database.

    This function safely migrates the schema by checking for column existence
    before attempting to add new columns.

    Args:
        database_path: Path to database file (uses config default if not specified)
    """
    db_path = database_path or config.database_path
    logger.info(f"Applying schema migrations to {db_path}")

    conn = get_connection(db_path)
    cursor = conn.cursor()

    migrations_applied = 0

    try:
        # Migrate property_observation_snapshots table (v2)
        for migration_sql in MIGRATE_PROPERTY_OBSERVATION_SNAPSHOTS_V2:
            # Extract column name from ALTER TABLE statement
            # Format: "ALTER TABLE property_observation_snapshots ADD COLUMN column_name TYPE;"
            parts = migration_sql.split()
            if "ADD" in parts and "COLUMN" in parts:
                column_idx = parts.index("COLUMN") + 1
                column_name = parts[column_idx]

                # Check if column already exists
                if not column_exists("property_observation_snapshots", column_name, db_path):
                    cursor.execute(migration_sql)
                    migrations_applied += 1
                    logger.info(f"Applied migration: Added column {column_name}")
                else:
                    logger.debug(f"Skipping migration: Column {column_name} already exists")

        conn.commit()
        logger.info(f"Schema migrations complete. Applied {migrations_applied} migrations.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error applying schema migrations: {e}")
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


# Candidate management functions


def find_candidate_by_url(
    redfin_url: str, database_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Find a candidate by Redfin URL.

    Args:
        redfin_url: Redfin URL to search for
        database_path: Path to database file

    Returns:
        Candidate row as dict or None
    """
    query = "SELECT * FROM candidate_review_queue WHERE redfin_url = ?"
    results = execute_query(query, (redfin_url,), database_path=database_path)
    return dict(results[0]) if results else None


def find_candidate_by_address(
    normalized_address: str, database_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Find a candidate by normalized address.

    Args:
        normalized_address: Normalized address to search for
        database_path: Path to database file

    Returns:
        Candidate row as dict or None
    """
    query = "SELECT * FROM candidate_review_queue WHERE normalized_address = ?"
    results = execute_query(query, (normalized_address,), database_path=database_path)
    return dict(results[0]) if results else None


def insert_candidate(
    candidate: CandidateProperty,
    skip_if_exists: bool = True,
    database_path: Optional[str] = None,
) -> Optional[int]:
    """
    Insert a candidate into the review queue.

    Args:
        candidate: Candidate property to insert
        skip_if_exists: If True, skip insertion if candidate already exists
        database_path: Path to database file

    Returns:
        Candidate ID of inserted row, or existing ID if skip_if_exists=True, or None if skipped
    """
    # Normalize address if not already normalized
    if candidate.normalized_address is None and candidate.address:
        candidate.normalized_address = normalize_address(candidate.address)

    # Check for existing candidate
    existing = None
    if skip_if_exists:
        existing = find_candidate_by_url(candidate.redfin_url, database_path)
        if not existing and candidate.normalized_address:
            existing = find_candidate_by_address(
                candidate.normalized_address, database_path
            )

    if existing:
        logger.info(
            f"Candidate already exists: {candidate.address} (ID: {existing['candidate_id']})"
        )
        return existing["candidate_id"]

    # Insert new candidate
    query = """
    INSERT INTO candidate_review_queue (
        discovery_date, source_site, source_search_url, redfin_url,
        address, normalized_address, city, zip, price, beds, baths,
        sqft, lot_size, displayed_dom, quiet_score, vibrancy_score,
        quiet_gatekeeper_result, garage_spaces, gas_service, gas_evidence,
        effective_dom_estimate, listing_churn_count, dom_reset_count,
        sale_rent_alternation_count, review_status, user_decision, user_notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        candidate.discovery_date,
        candidate.source_site,
        candidate.source_search_url,
        candidate.redfin_url,
        candidate.address,
        candidate.normalized_address,
        candidate.city,
        candidate.zip,
        candidate.price,
        candidate.beds,
        candidate.baths,
        candidate.sqft,
        candidate.lot_size,
        candidate.displayed_dom,
        candidate.quiet_score,
        candidate.vibrancy_score,
        candidate.quiet_gatekeeper_result,
        candidate.garage_spaces,
        candidate.gas_service,
        candidate.gas_evidence,
        candidate.effective_dom_estimate,
        candidate.listing_churn_count,
        candidate.dom_reset_count,
        candidate.sale_rent_alternation_count,
        candidate.review_status,
        candidate.user_decision,
        candidate.user_notes,
    )

    candidate_id = execute_insert(query, params, database_path=database_path)
    logger.info(f"Inserted candidate: {candidate.address} (ID: {candidate_id})")
    return candidate_id


def insert_candidates(
    candidates: List[CandidateProperty],
    skip_if_exists: bool = True,
    database_path: Optional[str] = None,
) -> List[int]:
    """
    Insert multiple candidates into the review queue.

    Args:
        candidates: List of candidate properties to insert
        skip_if_exists: If True, skip insertion if candidate already exists
        database_path: Path to database file

    Returns:
        List of candidate IDs (existing or new)
    """
    ids = []
    for candidate in candidates:
        candidate_id = insert_candidate(candidate, skip_if_exists, database_path)
        if candidate_id:
            ids.append(candidate_id)
    return ids


def get_all_candidates(database_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all candidates from the review queue.

    Args:
        database_path: Path to database file

    Returns:
        List of candidate rows as dicts
    """
    query = "SELECT * FROM candidate_review_queue ORDER BY created_at DESC"
    results = execute_query(query, database_path=database_path)
    return [dict(row) for row in results]


def get_candidates_by_status(
    status: str, database_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get candidates by review status.

    Args:
        status: Review status to filter by
        database_path: Path to database file

    Returns:
        List of candidate rows as dicts
    """
    query = "SELECT * FROM candidate_review_queue WHERE review_status = ? ORDER BY created_at DESC"
    results = execute_query(query, (status,), database_path=database_path)
    return [dict(row) for row in results]


def update_candidate_decision(
    candidate_id: int,
    user_decision: str,
    user_notes: Optional[str] = None,
    database_path: Optional[str] = None,
) -> None:
    """
    Update a candidate's review decision.

    Args:
        candidate_id: Candidate ID to update
        user_decision: User's decision (save, reject, maybe, hold_for_more_data)
        user_notes: Optional user notes
        database_path: Path to database file
    """
    query = """
    UPDATE candidate_review_queue
    SET user_decision = ?, user_notes = ?, review_status = 'reviewed', updated_at = CURRENT_TIMESTAMP
    WHERE candidate_id = ?
    """
    execute_update(query, (user_decision, user_notes, candidate_id), database_path=database_path)
    logger.info(f"Updated candidate {candidate_id} decision to: {user_decision}")


# Watched properties management functions


def find_watched_by_address(
    normalized_address: str, database_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Find a watched property by normalized address.

    Args:
        normalized_address: Normalized address to search for
        database_path: Path to database file

    Returns:
        Watched property row as dict or None
    """
    query = "SELECT * FROM watched_properties WHERE normalized_address = ?"
    results = execute_query(query, (normalized_address,), database_path=database_path)
    return dict(results[0]) if results else None


def insert_watched_property(
    watched: WatchedProperty, database_path: Optional[str] = None
) -> Optional[int]:
    """
    Insert a watched property.

    Args:
        watched: Watched property to insert
        database_path: Path to database file

    Returns:
        Property ID of inserted row, or existing ID if already exists
    """
    # Check for existing watched property
    if watched.normalized_address:
        existing = find_watched_by_address(watched.normalized_address, database_path)
        if existing:
            logger.info(
                f"Watched property already exists: {watched.address} (ID: {existing['property_id']})"
            )
            return existing["property_id"]

    # Insert new watched property
    query = """
    INSERT INTO watched_properties (
        first_saved_date, active_watch_status, redfin_url, zillow_url,
        realtor_url, homes_url, compass_url, address, normalized_address,
        city, zip, apn, current_price, original_observed_price, beds, baths,
        sqft, lot_size, garage_spaces, gas_service, gas_evidence, quiet_score,
        vibrancy_score, displayed_dom, effective_dom, effective_dom_delta,
        listing_churn_count, dom_reset_count, sale_rent_alternation_count,
        county_sale_verified, ownership_transfer_found, last_checked_date,
        next_check_date, watch_priority, user_notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        watched.first_saved_date,
        watched.active_watch_status,
        watched.redfin_url,
        watched.zillow_url,
        watched.realtor_url,
        watched.homes_url,
        watched.compass_url,
        watched.address,
        watched.normalized_address,
        watched.city,
        watched.zip,
        watched.apn,
        watched.current_price,
        watched.original_observed_price,
        watched.beds,
        watched.baths,
        watched.sqft,
        watched.lot_size,
        watched.garage_spaces,
        watched.gas_service,
        watched.gas_evidence,
        watched.quiet_score,
        watched.vibrancy_score,
        watched.displayed_dom,
        watched.effective_dom,
        watched.effective_dom_delta,
        watched.listing_churn_count,
        watched.dom_reset_count,
        watched.sale_rent_alternation_count,
        watched.county_sale_verified,
        watched.ownership_transfer_found,
        watched.last_checked_date,
        watched.next_check_date,
        watched.watch_priority,
        watched.user_notes,
    )

    property_id = execute_insert(query, params, database_path=database_path)
    logger.info(f"Inserted watched property: {watched.address} (ID: {property_id})")
    return property_id


def get_all_watched_properties(database_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all watched properties.

    Args:
        database_path: Path to database file

    Returns:
        List of watched property rows as dicts
    """
    query = "SELECT * FROM watched_properties ORDER BY first_saved_date DESC"
    results = execute_query(query, database_path=database_path)
    return [dict(row) for row in results]


def get_active_watched_properties(database_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get active watched properties.

    Args:
        database_path: Path to database file

    Returns:
        List of active watched property rows as dicts
    """
    query = "SELECT * FROM watched_properties WHERE active_watch_status = 1 ORDER BY first_saved_date DESC"
    results = execute_query(query, database_path=database_path)
    return [dict(row) for row in results]


def record_review_action(
    candidate_id: int,
    user_decision: str,
    user_notes: Optional[str] = None,
    promoted_property_id: Optional[int] = None,
    database_path: Optional[str] = None,
) -> int:
    """
    Record a user review action.

    Args:
        candidate_id: Candidate ID
        user_decision: User's decision
        user_notes: Optional user notes
        promoted_property_id: ID of promoted property if applicable
        database_path: Path to database file

    Returns:
        Review action ID
    """
    query = """
    INSERT INTO user_review_actions (
        candidate_id, user_decision, user_notes, promoted_property_id
    ) VALUES (?, ?, ?, ?)
    """
    return execute_insert(
        query,
        (candidate_id, user_decision, user_notes, promoted_property_id),
        database_path=database_path,
    )
