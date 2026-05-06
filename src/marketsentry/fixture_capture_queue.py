"""Fixture capture queue for Market_Sentry.

Manages a local queue of URLs/pages that need manual fixture capture.
When live retrieval is blocked or not implemented, the system tells
the user what local HTML fixture to save manually.

Uses a SQLite table for persistence and supports CSV export.

No network calls are performed by this module.
"""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from marketsentry.database import get_connection, init_db
from marketsentry.logging_config import logger
from marketsentry.source_adapters.dry_run_approval import normalize_url
from marketsentry.source_adapters.policy import (
    FixtureCaptureQueueResult,
    FixtureCaptureRequest,
    suggest_fixture_path,
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

CREATE_FIXTURE_CAPTURE_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS fixture_capture_queue (
    capture_request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_site TEXT NOT NULL,
    source_url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    request_type TEXT NOT NULL,
    suggested_fixture_path TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    reason TEXT,
    candidate_id INTEGER,
    property_id INTEGER,
    notes TEXT,
    captured_at TIMESTAMP,
    fixture_path TEXT
);
"""

CREATE_FIXTURE_CAPTURE_QUEUE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_fcq_status ON fixture_capture_queue(status);",
    "CREATE INDEX IF NOT EXISTS idx_fcq_source ON fixture_capture_queue(source_site);",
    "CREATE INDEX IF NOT EXISTS idx_fcq_normalized_url ON fixture_capture_queue(normalized_url);",
]


def ensure_fixture_capture_table(database_path: Optional[str] = None) -> None:
    """Create the fixture_capture_queue table if it doesn't exist.

    Args:
        database_path: Path to database file.
    """
    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(CREATE_FIXTURE_CAPTURE_QUEUE_TABLE)
        for idx_sql in CREATE_FIXTURE_CAPTURE_QUEUE_INDEXES:
            cursor.execute(idx_sql)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating fixture_capture_queue table: {e}")
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------


def add_capture_request(
    request: FixtureCaptureRequest,
    database_path: Optional[str] = None,
) -> FixtureCaptureQueueResult:
    """Add a fixture capture request to the queue.

    Deduplicates by source_site + normalized_url + request_type + pending status.

    Args:
        request: Fixture capture request to add.
        database_path: Path to database file.

    Returns:
        FixtureCaptureQueueResult with add status.
    """
    ensure_fixture_capture_table(database_path)

    normalized = normalize_url(request.source_url)

    # Suggest path if not provided
    suggested_path = request.suggested_fixture_path
    if not suggested_path:
        suggested_path = suggest_fixture_path(
            request.source_site, request.request_type, request.source_url
        )

    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        # Check for existing pending request with same source+url+type
        cursor.execute(
            """
            SELECT capture_request_id FROM fixture_capture_queue
            WHERE source_site = ? AND normalized_url = ? AND request_type = ? AND status = 'pending'
            """,
            (request.source_site, normalized, request.request_type),
        )
        existing = cursor.fetchone()

        if existing:
            return FixtureCaptureQueueResult(
                added=False,
                duplicate=True,
                capture_request_id=existing[0],
                message=f"Duplicate: pending request already exists (ID: {existing[0]}).",
            )

        # Insert new request
        cursor.execute(
            """
            INSERT INTO fixture_capture_queue (
                source_site, source_url, normalized_url, request_type,
                suggested_fixture_path, status, priority, reason,
                candidate_id, property_id, notes
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
            """,
            (
                request.source_site,
                request.source_url,
                normalized,
                request.request_type,
                suggested_path,
                request.priority,
                request.reason,
                request.candidate_id,
                request.property_id,
                request.notes,
            ),
        )
        conn.commit()
        capture_id = cursor.lastrowid

        logger.info(
            f"Added fixture capture request: {request.source_site} "
            f"{request.source_url} (ID: {capture_id})"
        )

        return FixtureCaptureQueueResult(
            added=True,
            duplicate=False,
            capture_request_id=capture_id,
            message=f"Capture request added (ID: {capture_id}).",
        )

    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding capture request: {e}")
        raise
    finally:
        conn.close()


def list_pending_capture_requests(
    source_site: Optional[str] = None,
    database_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List pending fixture capture requests.

    Args:
        source_site: Filter by source site. None for all.
        database_path: Path to database file.

    Returns:
        List of pending capture request rows.
    """
    ensure_fixture_capture_table(database_path)

    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        if source_site:
            cursor.execute(
                """
                SELECT * FROM fixture_capture_queue
                WHERE status = 'pending' AND source_site = ?
                ORDER BY priority ASC, created_at ASC
                """,
                (source_site,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM fixture_capture_queue
                WHERE status = 'pending'
                ORDER BY priority ASC, created_at ASC
                """
            )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_all_capture_requests(
    database_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all fixture capture requests regardless of status.

    Args:
        database_path: Path to database file.

    Returns:
        List of all capture request rows.
    """
    ensure_fixture_capture_table(database_path)

    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT * FROM fixture_capture_queue
            ORDER BY status ASC, priority ASC, created_at ASC
            """
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def mark_fixture_captured(
    capture_request_id: int,
    fixture_path: Optional[str] = None,
    database_path: Optional[str] = None,
) -> bool:
    """Mark a capture request as captured.

    Args:
        capture_request_id: ID of the capture request.
        fixture_path: Path to the captured fixture file.
        database_path: Path to database file.

    Returns:
        True if the request was found and updated.
    """
    ensure_fixture_capture_table(database_path)

    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE fixture_capture_queue
            SET status = 'captured', captured_at = ?, fixture_path = ?
            WHERE capture_request_id = ?
            """,
            (datetime.now().isoformat(), fixture_path or "", capture_request_id),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"Marked capture request {capture_request_id} as captured.")
        return updated
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking capture request: {e}")
        raise
    finally:
        conn.close()


def mark_fixture_skipped(
    capture_request_id: int,
    notes: Optional[str] = None,
    database_path: Optional[str] = None,
) -> bool:
    """Mark a capture request as skipped.

    Args:
        capture_request_id: ID of the capture request.
        notes: Optional notes about why it was skipped.
        database_path: Path to database file.

    Returns:
        True if the request was found and updated.
    """
    ensure_fixture_capture_table(database_path)

    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        if notes:
            cursor.execute(
                """
                UPDATE fixture_capture_queue
                SET status = 'skipped', notes = ?
                WHERE capture_request_id = ?
                """,
                (notes, capture_request_id),
            )
        else:
            cursor.execute(
                """
                UPDATE fixture_capture_queue
                SET status = 'skipped'
                WHERE capture_request_id = ?
                """,
                (capture_request_id,),
            )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking capture request as skipped: {e}")
        raise
    finally:
        conn.close()


def get_capture_request_count(
    status: Optional[str] = None,
    database_path: Optional[str] = None,
) -> int:
    """Get count of capture requests.

    Args:
        status: Filter by status. None for all.
        database_path: Path to database file.

    Returns:
        Count of matching requests.
    """
    ensure_fixture_capture_table(database_path)

    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        if status:
            cursor.execute(
                "SELECT COUNT(*) FROM fixture_capture_queue WHERE status = ?",
                (status,),
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM fixture_capture_queue")
        return cursor.fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


EXPORT_FIELDNAMES = [
    "capture_request_id",
    "created_at",
    "source_site",
    "source_url",
    "normalized_url",
    "request_type",
    "suggested_fixture_path",
    "status",
    "priority",
    "reason",
    "candidate_id",
    "property_id",
    "notes",
    "captured_at",
    "fixture_path",
]


def export_capture_queue_csv(
    output_dir: Optional[str] = None,
    include_all: bool = True,
    database_path: Optional[str] = None,
) -> str:
    """Export the fixture capture queue to a CSV file.

    Args:
        output_dir: Output directory. Defaults to data/exports/.
        include_all: If True, include all statuses. If False, pending only.
        database_path: Path to database file.

    Returns:
        Path to the exported CSV file.
    """
    export_dir = Path(output_dir or "data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = export_dir / f"fixture_capture_queue_{timestamp}.csv"

    if include_all:
        rows = list_all_capture_requests(database_path)
    else:
        rows = list_pending_capture_requests(database_path=database_path)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    logger.info(f"Exported {len(rows)} capture requests to {output_file}")
    return str(output_file)
