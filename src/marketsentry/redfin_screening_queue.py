"""Redfin initial screening queue for operator property screening.

Manages a local pre-candidate screening queue with clickable Redfin
links and Save for Analysis workflow. Properties enter via CSV or
saved search fixture import, get screened by the operator, and are
promoted to the candidate_review_queue via explicit Save for Analysis.

This module does NOT perform live retrieval, send outbound
notifications, or modify the Quiet Score gatekeeper.
All actions are local-only and operator-initiated.
"""

import csv
import io
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from marketsentry.config import config


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------


class RedfinScreeningItem(BaseModel):
    """A single item in the Redfin screening queue."""

    screening_id: int = 0
    redfin_url: str = ""
    normalized_redfin_url: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: str = "CA"
    zip: Optional[str] = None
    price: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_size: Optional[float] = None
    displayed_dom: Optional[int] = None
    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    status: str = "new"
    user_screening_decision: str = "new"
    user_notes: Optional[str] = None
    source_file: Optional[str] = None
    source_type: Optional[str] = None
    opened_at: Optional[str] = None
    saved_for_analysis_at: Optional[str] = None
    candidate_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RedfinScreeningImportResult(BaseModel):
    """Result of importing URLs into the screening queue."""

    total_rows_read: int = 0
    items_inserted: int = 0
    items_skipped: int = 0
    items_rejected: int = 0
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    source_file: str = ""
    source_type: str = ""


class RedfinScreeningActionResult(BaseModel):
    """Result of a screening queue action."""

    screening_id: int = 0
    action: str = ""
    success: bool = False
    detail: str = ""
    candidate_id: Optional[int] = None


class RedfinScreeningQueueSummary(BaseModel):
    """Summary of the screening queue state."""

    total: int = 0
    new: int = 0
    opened: int = 0
    saved_for_analysis: int = 0
    rejected: int = 0
    hold: int = 0
    duplicate: int = 0
    error: int = 0


class RedfinScreeningReportRow(BaseModel):
    """A row in the screening queue report."""

    screening_id: int = 0
    address: Optional[str] = None
    city: Optional[str] = None
    price: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    status: str = ""
    decision: str = ""
    candidate_id: Optional[int] = None
    redfin_url: str = ""
    user_notes: Optional[str] = None
    saved_for_analysis: bool = False
    candidate_has_enrichment: bool = False
    candidate_has_quiet_vibrancy: bool = False
    candidate_watchlisted: bool = False
    next_step: str = ""


class RedfinScreeningBatchActionRequest(BaseModel):
    """A request to apply one action to several screening items."""

    screening_ids: List[int] = Field(default_factory=list)
    action: str = ""
    notes: Optional[str] = None
    refresh: bool = False


class RedfinScreeningBatchActionResult(BaseModel):
    """Outcome of a batch screening action.

    Reports per-item success or failure. One failing item does not
    stop the remaining items from being processed.
    """

    action: str = ""
    requested_entries: List[str] = Field(default_factory=list)
    valid_ids: List[int] = Field(default_factory=list)
    duplicate_ids: List[int] = Field(default_factory=list)
    invalid_entries: List[str] = Field(default_factory=list)
    missing_ids: List[int] = Field(default_factory=list)
    item_results: List[RedfinScreeningActionResult] = Field(
        default_factory=list
    )
    refresh_requested: bool = False
    refresh_ran: bool = False
    refresh_output_paths: List[str] = Field(default_factory=list)
    refresh_error: Optional[str] = None
    errors: List[str] = Field(default_factory=list)

    @property
    def succeeded_count(self) -> int:
        """Number of items the action succeeded on."""
        return len([r for r in self.item_results if r.success])

    @property
    def failed_count(self) -> int:
        """Number of items the action failed on."""
        return len([r for r in self.item_results if not r.success])

    @property
    def created_candidate_ids(self) -> List[int]:
        """Candidate IDs created or linked by this batch."""
        return [
            r.candidate_id
            for r in self.item_results
            if r.success and r.candidate_id is not None
        ]


class RedfinScreeningNextStep(BaseModel):
    """One recommended next operator step.

    Analytical guidance only. Never a purchase recommendation.
    """

    step_id: str = ""
    category: str = ""
    message: str = ""
    count: int = 0
    command: str = ""
    severity: str = "info"


class RedfinScreeningOperatorStatus(BaseModel):
    """Combined screening and candidate status for the operator."""

    queue: RedfinScreeningQueueSummary = Field(
        default_factory=RedfinScreeningQueueSummary
    )
    saved_missing_enrichment: int = 0
    candidates_missing_quiet_vibrancy: int = 0
    candidates_failing_gatekeeper: int = 0
    candidates_ready_for_decision: int = 0
    watchlist_ready: int = 0
    next_steps: List[RedfinScreeningNextStep] = Field(
        default_factory=list
    )
    warnings: List[str] = Field(default_factory=list)


# -------------------------------------------------------------------
# Valid statuses and decisions
# -------------------------------------------------------------------

VALID_SCREENING_STATUSES = {
    "new", "opened", "saved_for_analysis",
    "rejected", "hold", "duplicate", "error",
}


# -------------------------------------------------------------------
# Schema
# -------------------------------------------------------------------


def ensure_redfin_screening_queue_schema(
    db_path: Optional[str] = None,
) -> None:
    """Create the redfin_screening_queue table if not exists.

    Idempotent. Safe to call multiple times.

    Args:
        db_path: Path to SQLite database.
    """
    if db_path is None:
        db_path = config.database_path

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS redfin_screening_queue (
            screening_id INTEGER PRIMARY KEY AUTOINCREMENT,
            redfin_url TEXT NOT NULL,
            normalized_redfin_url TEXT,
            address TEXT,
            city TEXT,
            state TEXT DEFAULT 'CA',
            zip TEXT,
            price REAL,
            beds INTEGER,
            baths REAL,
            sqft INTEGER,
            lot_size REAL,
            displayed_dom INTEGER,
            quiet_score REAL,
            vibrancy_score REAL,
            status TEXT DEFAULT 'new',
            user_screening_decision TEXT DEFAULT 'new',
            user_notes TEXT,
            source_file TEXT,
            source_type TEXT,
            opened_at TIMESTAMP,
            saved_for_analysis_at TIMESTAMP,
            candidate_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_screening_normalized_url
        ON redfin_screening_queue(normalized_redfin_url)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_screening_status
        ON redfin_screening_queue(status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_screening_decision
        ON redfin_screening_queue(user_screening_decision)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_screening_candidate_id
        ON redfin_screening_queue(candidate_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_screening_created_at
        ON redfin_screening_queue(created_at)
    """)
    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# Import functions
# -------------------------------------------------------------------


def import_redfin_screening_urls(
    csv_file_path: str,
    db_path: Optional[str] = None,
) -> RedfinScreeningImportResult:
    """Import Redfin URLs from CSV into the screening queue.

    Deduplicates by normalized Redfin URL. Does not insert
    into candidate_review_queue. Local-only, no live retrieval.

    CSV must have a 'redfin_url' column. Optional columns:
    address, city, price, beds, baths, sqft, notes.

    Args:
        csv_file_path: Path to CSV file.
        db_path: Path to SQLite database.

    Returns:
        Import result with counts and any warnings/errors.
    """
    if db_path is None:
        db_path = config.database_path

    result = RedfinScreeningImportResult(
        source_file=csv_file_path,
        source_type="csv",
    )

    csv_path = Path(csv_file_path)
    if not csv_path.is_file():
        result.errors.append(
            f"CSV file not found: {csv_file_path}"
        )
        return result

    ensure_redfin_screening_queue_schema(db_path=db_path)

    from marketsentry.redfin_url_utils import (
        extract_address_from_redfin_url,
        extract_city_from_redfin_url,
        extract_zip_from_redfin_url,
        is_redfin_url,
        normalize_redfin_url,
    )

    try:
        with open(csv_file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        result.errors.append(f"CSV read error: {e}")
        return result

    result.total_rows_read = len(rows)

    conn = sqlite3.connect(db_path)

    for row in rows:
        raw_url = row.get("redfin_url", "").strip()
        if not raw_url:
            raw_url = row.get("url", "").strip()

        if not raw_url:
            result.items_rejected += 1
            result.warnings.append(
                "Row missing redfin_url"
            )
            continue

        if not is_redfin_url(raw_url):
            result.items_rejected += 1
            result.warnings.append(
                f"Invalid Redfin URL: {raw_url[:80]}"
            )
            continue

        normalized = normalize_redfin_url(raw_url)

        # Check for duplicate
        cur = conn.cursor()
        cur.execute(
            "SELECT screening_id FROM "
            "redfin_screening_queue "
            "WHERE normalized_redfin_url = ?",
            (normalized,),
        )
        existing = cur.fetchone()
        if existing:
            result.items_skipped += 1
            continue

        # Extract data from URL if not in CSV
        address = (
            row.get("address", "").strip()
            or extract_address_from_redfin_url(raw_url)
            or ""
        )
        city = (
            row.get("city", "").strip()
            or extract_city_from_redfin_url(raw_url)
            or ""
        )
        zip_code = (
            row.get("zip", "").strip()
            or extract_zip_from_redfin_url(raw_url)
            or ""
        )

        price = _parse_float(row.get("price", ""))
        beds = _parse_int(row.get("beds", ""))
        baths = _parse_float(row.get("baths", ""))
        sqft = _parse_int(row.get("sqft", ""))
        notes = row.get("notes", "").strip() or None

        cur.execute(
            "INSERT INTO redfin_screening_queue "
            "(redfin_url, normalized_redfin_url, "
            "address, city, zip, price, beds, baths, "
            "sqft, user_notes, source_file, "
            "source_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                raw_url,
                normalized,
                address,
                city,
                zip_code,
                price,
                beds,
                baths,
                sqft,
                notes,
                csv_file_path,
                "csv",
            ),
        )
        result.items_inserted += 1

    conn.commit()
    conn.close()
    return result


def import_redfin_screening_fixture(
    fixture_path: str,
    db_path: Optional[str] = None,
) -> RedfinScreeningImportResult:
    """Import Redfin URLs from a saved search HTML fixture.

    Parses saved Redfin search HTML to extract property URLs
    and inserts them into the screening queue. Local-only
    fixture parsing, not live retrieval.

    Args:
        fixture_path: Path to saved Redfin search HTML file.
        db_path: Path to SQLite database.

    Returns:
        Import result with counts and warnings.
    """
    if db_path is None:
        db_path = config.database_path

    result = RedfinScreeningImportResult(
        source_file=fixture_path,
        source_type="fixture",
    )

    fix_path = Path(fixture_path)
    if not fix_path.is_file():
        result.errors.append(
            f"Fixture file not found: {fixture_path}"
        )
        return result

    ensure_redfin_screening_queue_schema(db_path=db_path)

    from marketsentry.redfin_url_utils import (
        extract_address_from_redfin_url,
        extract_city_from_redfin_url,
        extract_zip_from_redfin_url,
        is_redfin_url,
        normalize_redfin_url,
    )

    # Parse HTML to extract Redfin URLs
    try:
        html_content = fix_path.read_text(
            encoding="utf-8", errors="replace"
        )
    except Exception as e:
        result.errors.append(f"File read error: {e}")
        return result

    # Extract URLs from href attributes
    import re

    url_pattern = re.compile(
        r'href="(/[A-Z]{2}/[^"]+/home/\d+)"'
    )
    matches = url_pattern.findall(html_content)

    # Also try full URLs
    full_url_pattern = re.compile(
        r'href="(https?://(?:www\.)?redfin\.com'
        r'/[A-Z]{2}/[^"]+/home/\d+)"'
    )
    full_matches = full_url_pattern.findall(html_content)

    all_urls: List[str] = []
    for match in matches:
        full = f"https://www.redfin.com{match}"
        if is_redfin_url(full):
            all_urls.append(full)
    for match in full_matches:
        if is_redfin_url(match):
            all_urls.append(match)

    # Deduplicate within fixture
    seen: set[str] = set()
    unique_urls: List[str] = []
    for url in all_urls:
        normalized = normalize_redfin_url(url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_urls.append(url)

    result.total_rows_read = len(unique_urls)

    conn = sqlite3.connect(db_path)

    for raw_url in unique_urls:
        normalized = normalize_redfin_url(raw_url)

        # Check for duplicate
        cur = conn.cursor()
        cur.execute(
            "SELECT screening_id FROM "
            "redfin_screening_queue "
            "WHERE normalized_redfin_url = ?",
            (normalized,),
        )
        existing = cur.fetchone()
        if existing:
            result.items_skipped += 1
            continue

        address = (
            extract_address_from_redfin_url(raw_url)
            or ""
        )
        city = (
            extract_city_from_redfin_url(raw_url)
            or ""
        )
        zip_code = (
            extract_zip_from_redfin_url(raw_url)
            or ""
        )

        cur.execute(
            "INSERT INTO redfin_screening_queue "
            "(redfin_url, normalized_redfin_url, "
            "address, city, zip, source_file, "
            "source_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                raw_url,
                normalized,
                address,
                city,
                zip_code,
                fixture_path,
                "fixture",
            ),
        )
        result.items_inserted += 1

    conn.commit()
    conn.close()
    return result


# -------------------------------------------------------------------
# Query functions
# -------------------------------------------------------------------


def list_redfin_screening_items(
    db_path: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100,
) -> List[RedfinScreeningItem]:
    """List items from the screening queue.

    Args:
        db_path: Path to SQLite database.
        status_filter: Filter by status if provided.
        limit: Maximum items to return.

    Returns:
        List of screening items.
    """
    if db_path is None:
        db_path = config.database_path

    ensure_redfin_screening_queue_schema(db_path=db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if status_filter and status_filter in VALID_SCREENING_STATUSES:
        rows = conn.execute(
            "SELECT * FROM redfin_screening_queue "
            "WHERE status = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (status_filter, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM redfin_screening_queue "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    conn.close()

    items: List[RedfinScreeningItem] = []
    for row in rows:
        items.append(
            RedfinScreeningItem(
                screening_id=row["screening_id"],
                redfin_url=row["redfin_url"],
                normalized_redfin_url=row[
                    "normalized_redfin_url"
                ],
                address=row["address"],
                city=row["city"],
                state=row["state"] or "CA",
                zip=row["zip"],
                price=row["price"],
                beds=row["beds"],
                baths=row["baths"],
                sqft=row["sqft"],
                lot_size=row["lot_size"],
                displayed_dom=row["displayed_dom"],
                quiet_score=row["quiet_score"],
                vibrancy_score=row["vibrancy_score"],
                status=row["status"],
                user_screening_decision=row[
                    "user_screening_decision"
                ],
                user_notes=row["user_notes"],
                source_file=row["source_file"],
                source_type=row["source_type"],
                opened_at=row["opened_at"],
                saved_for_analysis_at=row[
                    "saved_for_analysis_at"
                ],
                candidate_id=row["candidate_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )

    return items


def summarize_redfin_screening_queue(
    db_path: Optional[str] = None,
) -> RedfinScreeningQueueSummary:
    """Get summary counts for the screening queue.

    Args:
        db_path: Path to SQLite database.

    Returns:
        Queue summary with status counts.
    """
    if db_path is None:
        db_path = config.database_path

    ensure_redfin_screening_queue_schema(db_path=db_path)
    summary = RedfinScreeningQueueSummary()

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM "
            "redfin_screening_queue"
        )
        summary.total = cur.fetchone()[0]

        for status_val, attr in [
            ("new", "new"),
            ("opened", "opened"),
            ("saved_for_analysis", "saved_for_analysis"),
            ("rejected", "rejected"),
            ("hold", "hold"),
            ("duplicate", "duplicate"),
            ("error", "error"),
        ]:
            cur.execute(
                "SELECT COUNT(*) FROM "
                "redfin_screening_queue "
                "WHERE status = ?",
                (status_val,),
            )
            setattr(summary, attr, cur.fetchone()[0])

        conn.close()
    except Exception:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return summary


# -------------------------------------------------------------------
# Action functions
# -------------------------------------------------------------------


def save_screening_item_for_analysis(
    screening_id: int,
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
) -> RedfinScreeningActionResult:
    """Save a screening item for full candidate analysis.

    Inserts the item into candidate_review_queue using
    existing insertion/dedup logic, then marks the
    screening item as saved_for_analysis. Does not
    duplicate candidates if URL already exists.

    Args:
        screening_id: Screening item ID.
        notes: Optional notes.
        db_path: Path to SQLite database.

    Returns:
        Action result with candidate_id if created.
    """
    if db_path is None:
        db_path = config.database_path

    result = RedfinScreeningActionResult(
        screening_id=screening_id,
        action="save_for_analysis",
    )

    ensure_redfin_screening_queue_schema(db_path=db_path)

    # Load screening item
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM redfin_screening_queue "
        "WHERE screening_id = ?",
        (screening_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        result.detail = (
            f"Screening item {screening_id} not found"
        )
        return result

    if row["status"] == "saved_for_analysis":
        result.success = True
        result.candidate_id = row["candidate_id"]
        result.detail = (
            f"Already saved for analysis "
            f"(candidate {row['candidate_id']})"
        )
        return result

    # Create candidate using existing logic
    from marketsentry.database import insert_candidate
    from marketsentry.models import CandidateProperty

    candidate = CandidateProperty(
        source_site="redfin",
        source_search_url="",
        redfin_url=row["redfin_url"],
        address=row["address"] or "",
        city=row["city"] or "",
        zip=row["zip"] or "",
        price=row["price"],
        beds=row["beds"],
        baths=row["baths"],
        sqft=row["sqft"],
        lot_size=row["lot_size"],
        displayed_dom=row["displayed_dom"],
        quiet_score=row["quiet_score"],
        vibrancy_score=row["vibrancy_score"],
    )

    candidate_id = insert_candidate(
        candidate,
        skip_if_exists=True,
        database_path=db_path,
    )

    # Update screening item
    combined_notes = row["user_notes"] or ""
    if notes:
        if combined_notes:
            combined_notes = f"{combined_notes}\n{notes}"
        else:
            combined_notes = notes

    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE redfin_screening_queue "
        "SET status = 'saved_for_analysis', "
        "user_screening_decision = "
        "'saved_for_analysis', "
        "candidate_id = ?, "
        "user_notes = ?, "
        "saved_for_analysis_at = "
        "CURRENT_TIMESTAMP, "
        "updated_at = CURRENT_TIMESTAMP "
        "WHERE screening_id = ?",
        (
            candidate_id,
            combined_notes or None,
            screening_id,
        ),
    )
    conn.commit()
    conn.close()

    result.success = True
    result.candidate_id = candidate_id
    result.detail = (
        f"Saved for analysis as candidate "
        f"{candidate_id}"
    )
    return result


def reject_screening_item(
    screening_id: int,
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
) -> RedfinScreeningActionResult:
    """Reject a screening item.

    Args:
        screening_id: Screening item ID.
        notes: Optional rejection notes.
        db_path: Path to SQLite database.

    Returns:
        Action result.
    """
    return _update_screening_status(
        screening_id=screening_id,
        new_status="rejected",
        action="reject",
        notes=notes,
        db_path=db_path,
    )


def hold_screening_item(
    screening_id: int,
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
) -> RedfinScreeningActionResult:
    """Hold a screening item for later review.

    Args:
        screening_id: Screening item ID.
        notes: Optional hold notes.
        db_path: Path to SQLite database.

    Returns:
        Action result.
    """
    return _update_screening_status(
        screening_id=screening_id,
        new_status="hold",
        action="hold",
        notes=notes,
        db_path=db_path,
    )


def mark_screening_item_opened(
    screening_id: int,
    db_path: Optional[str] = None,
) -> RedfinScreeningActionResult:
    """Mark a screening item as opened (link clicked).

    Args:
        screening_id: Screening item ID.
        db_path: Path to SQLite database.

    Returns:
        Action result.
    """
    if db_path is None:
        db_path = config.database_path

    result = RedfinScreeningActionResult(
        screening_id=screening_id,
        action="mark_opened",
    )

    ensure_redfin_screening_queue_schema(db_path=db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM redfin_screening_queue "
        "WHERE screening_id = ?",
        (screening_id,),
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        result.detail = (
            f"Screening item {screening_id} not found"
        )
        return result

    # Only update if still new
    if row["status"] == "new":
        conn.execute(
            "UPDATE redfin_screening_queue "
            "SET status = 'opened', "
            "user_screening_decision = 'opened', "
            "opened_at = CURRENT_TIMESTAMP, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE screening_id = ?",
            (screening_id,),
        )
        conn.commit()

    conn.close()
    result.success = True
    result.detail = f"Item {screening_id} marked opened"
    return result


# -------------------------------------------------------------------
# Batch actions
# -------------------------------------------------------------------


def parse_screening_id_list(
    raw: str,
) -> Tuple[List[int], List[str], List[int]]:
    """Parse a comma-separated screening ID list.

    Accepts forms such as "4,5,6" or "4, 5, 6". Order of first
    appearance is preserved. Repeated IDs are reported separately
    rather than actioned twice.

    Args:
        raw: Comma-separated ID string.

    Returns:
        Tuple of (unique_ids, invalid_entries, duplicate_ids).
    """
    unique_ids: List[int] = []
    invalid_entries: List[str] = []
    duplicate_ids: List[int] = []

    if raw is None:
        return unique_ids, invalid_entries, duplicate_ids

    for entry in str(raw).split(","):
        cleaned = entry.strip()
        if not cleaned:
            continue
        try:
            value = int(cleaned)
        except (ValueError, TypeError):
            invalid_entries.append(cleaned)
            continue
        if value in unique_ids:
            duplicate_ids.append(value)
            continue
        unique_ids.append(value)

    return unique_ids, invalid_entries, duplicate_ids


def _existing_screening_ids(
    screening_ids: List[int],
    db_path: str,
) -> List[int]:
    """Return the subset of IDs that exist in the queue."""
    if not screening_ids:
        return []

    conn = sqlite3.connect(db_path)
    try:
        placeholders = ",".join("?" for _ in screening_ids)
        rows = conn.execute(
            "SELECT screening_id FROM redfin_screening_queue "
            f"WHERE screening_id IN ({placeholders})",  # noqa: S608
            tuple(screening_ids),
        ).fetchall()
    finally:
        conn.close()

    return [r[0] for r in rows]


def _run_batch(
    screening_ids: List[int],
    action: str,
    single_action: Callable[..., RedfinScreeningActionResult],
    notes: Optional[str],
    db_path: Optional[str],
    duplicate_ids: Optional[List[int]] = None,
    invalid_entries: Optional[List[str]] = None,
) -> RedfinScreeningBatchActionResult:
    """Apply one single-item action across a list of IDs.

    Each item is processed independently so a failure on one ID
    does not prevent the remaining IDs from being actioned.
    """
    path = db_path or config.database_path

    result = RedfinScreeningBatchActionResult(
        action=action,
        duplicate_ids=list(duplicate_ids or []),
        invalid_entries=list(invalid_entries or []),
    )

    if not screening_ids:
        result.errors.append(
            "No valid screening IDs supplied."
        )
        return result

    ensure_redfin_screening_queue_schema(db_path=path)

    existing = set(_existing_screening_ids(screening_ids, path))
    for screening_id in screening_ids:
        if screening_id not in existing:
            result.missing_ids.append(screening_id)
            result.item_results.append(
                RedfinScreeningActionResult(
                    screening_id=screening_id,
                    action=action,
                    success=False,
                    detail=(
                        f"Screening item {screening_id} not found"
                    ),
                )
            )
            continue

        result.valid_ids.append(screening_id)
        try:
            if notes is None:
                item_result = single_action(
                    screening_id, db_path=path
                )
            else:
                item_result = single_action(
                    screening_id, notes=notes, db_path=path
                )
            result.item_results.append(item_result)
        except Exception as exc:  # pragma: no cover - defensive
            result.item_results.append(
                RedfinScreeningActionResult(
                    screening_id=screening_id,
                    action=action,
                    success=False,
                    detail=f"Error: {exc}",
                )
            )

    return result


def _maybe_refresh(
    result: RedfinScreeningBatchActionResult,
    refresh: bool,
    db_path: Optional[str],
    exports_dir: Optional[str],
) -> RedfinScreeningBatchActionResult:
    """Optionally run the local operator refresh workflow.

    A refresh failure is recorded but never rolls back the batch
    actions that already succeeded.
    """
    result.refresh_requested = refresh
    if not refresh:
        return result

    try:
        from marketsentry.operator_workflow import (
            run_operator_refresh_workflow,
        )

        run_result = run_operator_refresh_workflow(
            db_path=db_path or config.database_path,
            exports_dir=exports_dir,
        )
        result.refresh_ran = True
        result.refresh_output_paths = list(
            run_result.output_paths
        )
    except Exception as exc:
        result.refresh_ran = False
        result.refresh_error = str(exc)

    return result


def batch_save_screening_items_for_analysis(
    screening_ids: List[int],
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
    refresh: bool = False,
    exports_dir: Optional[str] = None,
    duplicate_ids: Optional[List[int]] = None,
    invalid_entries: Optional[List[str]] = None,
) -> RedfinScreeningBatchActionResult:
    """Save several screening items for analysis.

    Creates or links a candidate per item using the same dedup
    logic as the single-item action. This remains an explicit
    operator action; imports never call it.

    Args:
        screening_ids: Screening item IDs.
        notes: Optional notes appended to each item.
        db_path: Path to SQLite database.
        refresh: Run the local refresh workflow afterwards.
        exports_dir: Exports directory for the refresh.
        duplicate_ids: Duplicate IDs detected during parsing.
        invalid_entries: Invalid entries detected during parsing.

    Returns:
        Batch result with per-item outcomes.
    """
    result = _run_batch(
        screening_ids=screening_ids,
        action="save_for_analysis",
        single_action=save_screening_item_for_analysis,
        notes=notes,
        db_path=db_path,
        duplicate_ids=duplicate_ids,
        invalid_entries=invalid_entries,
    )
    return _maybe_refresh(
        result, refresh, db_path, exports_dir
    )


def batch_reject_screening_items(
    screening_ids: List[int],
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
    duplicate_ids: Optional[List[int]] = None,
    invalid_entries: Optional[List[str]] = None,
) -> RedfinScreeningBatchActionResult:
    """Reject several screening items.

    Args:
        screening_ids: Screening item IDs.
        notes: Optional notes appended to each item.
        db_path: Path to SQLite database.
        duplicate_ids: Duplicate IDs detected during parsing.
        invalid_entries: Invalid entries detected during parsing.

    Returns:
        Batch result with per-item outcomes.
    """
    return _run_batch(
        screening_ids=screening_ids,
        action="reject",
        single_action=reject_screening_item,
        notes=notes,
        db_path=db_path,
        duplicate_ids=duplicate_ids,
        invalid_entries=invalid_entries,
    )


def batch_hold_screening_items(
    screening_ids: List[int],
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
    duplicate_ids: Optional[List[int]] = None,
    invalid_entries: Optional[List[str]] = None,
) -> RedfinScreeningBatchActionResult:
    """Hold several screening items for later review.

    Args:
        screening_ids: Screening item IDs.
        notes: Optional notes appended to each item.
        db_path: Path to SQLite database.
        duplicate_ids: Duplicate IDs detected during parsing.
        invalid_entries: Invalid entries detected during parsing.

    Returns:
        Batch result with per-item outcomes.
    """
    return _run_batch(
        screening_ids=screening_ids,
        action="hold",
        single_action=hold_screening_item,
        notes=notes,
        db_path=db_path,
        duplicate_ids=duplicate_ids,
        invalid_entries=invalid_entries,
    )


def batch_mark_screening_items_opened(
    screening_ids: List[int],
    db_path: Optional[str] = None,
    duplicate_ids: Optional[List[int]] = None,
    invalid_entries: Optional[List[str]] = None,
) -> RedfinScreeningBatchActionResult:
    """Mark several screening items as opened.

    Args:
        screening_ids: Screening item IDs.
        db_path: Path to SQLite database.
        duplicate_ids: Duplicate IDs detected during parsing.
        invalid_entries: Invalid entries detected during parsing.

    Returns:
        Batch result with per-item outcomes.
    """
    return _run_batch(
        screening_ids=screening_ids,
        action="mark_opened",
        single_action=mark_screening_item_opened,
        notes=None,
        db_path=db_path,
        duplicate_ids=duplicate_ids,
        invalid_entries=invalid_entries,
    )


# -------------------------------------------------------------------
# Next-step guidance
# -------------------------------------------------------------------


def _collect_operator_counts(db_path: str) -> Dict[str, int]:
    """Gather counts used to derive next steps."""
    counts = {
        "saved_missing_enrichment": 0,
        "candidates_missing_quiet_vibrancy": 0,
        "candidates_failing_gatekeeper": 0,
        "candidates_ready_for_decision": 0,
        "watchlist_ready": 0,
    }

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        def _table_exists(name: str) -> bool:
            return cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name=?",
                (name,),
            ).fetchone() is not None

        has_candidates = _table_exists("candidate_review_queue")
        has_screening = _table_exists("redfin_screening_queue")

        if has_screening and has_candidates:
            # Saved for analysis but candidate lacks enrichment.
            cur.execute(
                "SELECT COUNT(*) FROM redfin_screening_queue s "
                "JOIN candidate_review_queue c "
                "ON s.candidate_id = c.candidate_id "
                "WHERE s.status = 'saved_for_analysis' "
                "AND c.beds IS NULL "
                "AND c.baths IS NULL "
                "AND c.sqft IS NULL"
            )
            counts["saved_missing_enrichment"] = cur.fetchone()[0]

        if has_candidates:
            cur.execute(
                "SELECT COUNT(*) FROM candidate_review_queue "
                "WHERE quiet_score IS NULL "
                "OR vibrancy_score IS NULL"
            )
            counts["candidates_missing_quiet_vibrancy"] = (
                cur.fetchone()[0]
            )

            cur.execute(
                "SELECT COUNT(*) FROM candidate_review_queue "
                "WHERE quiet_gatekeeper_result = "
                "'fail_noise_risk'"
            )
            counts["candidates_failing_gatekeeper"] = (
                cur.fetchone()[0]
            )

            cur.execute(
                "SELECT COUNT(*) FROM candidate_review_queue "
                "WHERE review_status = 'pending' "
                "AND quiet_score IS NOT NULL "
                "AND vibrancy_score IS NOT NULL"
            )
            counts["candidates_ready_for_decision"] = (
                cur.fetchone()[0]
            )

            cur.execute(
                "SELECT COUNT(*) FROM candidate_review_queue "
                "WHERE user_decision = 'save'"
            )
            counts["watchlist_ready"] = cur.fetchone()[0]
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return counts


def _name_candidates(
    db_path: str,
    which: str,
    limit: int = 5,
) -> str:
    """Name the specific candidates behind a next-step count.

    A bare count tells the operator work exists but not which
    property to open. Returns a short suffix such as
    " Candidate 7 - 31801 Valone Ct; Candidate 8 - ...".
    """
    try:
        from marketsentry.manual_score_entry import (
            list_candidates_failing_gatekeeper,
            list_candidates_needing_scores,
        )

        if which == "failing_gatekeeper":
            statuses = list_candidates_failing_gatekeeper(
                db_path=db_path
            )
        else:
            statuses = list_candidates_needing_scores(
                db_path=db_path
            )
    except Exception:  # pragma: no cover - defensive
        return ""

    if not statuses:
        return ""

    named = [
        f"Candidate {s.candidate_id} - {s.address or 'unknown'}"
        for s in statuses[:limit]
    ]
    suffix = "; ".join(named)
    if len(statuses) > limit:
        suffix += f"; and {len(statuses) - limit} more"
    return f" {suffix}."


def build_screening_next_steps(
    db_path: Optional[str] = None,
) -> List[RedfinScreeningNextStep]:
    """Build the ordered list of recommended operator steps.

    Steps describe required data-gathering actions only. They never
    recommend buying, offering on, or valuing a property.

    Args:
        db_path: Path to SQLite database.

    Returns:
        Ordered list of next steps, most immediate first.
    """
    path = db_path or config.database_path
    ensure_redfin_screening_queue_schema(db_path=path)

    summary = summarize_redfin_screening_queue(db_path=path)
    counts = _collect_operator_counts(path)
    steps: List[RedfinScreeningNextStep] = []

    if summary.new:
        steps.append(
            RedfinScreeningNextStep(
                step_id="open_new_items",
                category="screening",
                message=(
                    "New screening items: open the Redfin link "
                    "and visually inspect the property."
                ),
                count=summary.new,
                command=(
                    "marketsentry batch-mark-screening-items-"
                    "opened --screening-ids <ids>"
                ),
                severity="action",
            )
        )

    if summary.opened:
        steps.append(
            RedfinScreeningNextStep(
                step_id="decide_opened_items",
                category="screening",
                message=(
                    "Opened but undecided: choose Save for "
                    "Analysis, Hold, or Reject."
                ),
                count=summary.opened,
                command=(
                    "marketsentry batch-save-screening-items "
                    "--screening-ids <ids>"
                ),
                severity="action",
            )
        )

    if counts["saved_missing_enrichment"]:
        steps.append(
            RedfinScreeningNextStep(
                step_id="save_detail_html",
                category="candidate",
                message=(
                    "Saved for analysis but missing Redfin "
                    "detail HTML: save the Redfin detail page to "
                    "data/raw/redfin/details and run enrichment."
                ),
                count=counts["saved_missing_enrichment"],
                command=(
                    "marketsentry enrich-redfin-details "
                    "--dir data/raw/redfin/details"
                ),
                severity="action",
            )
        )

    if counts["candidates_missing_quiet_vibrancy"]:
        steps.append(
            RedfinScreeningNextStep(
                step_id="capture_quiet_vibrancy",
                category="candidate",
                message=(
                    "Candidates missing Quiet/Vibrancy: open the "
                    "Redfin page, visually read Quiet and Vibrancy, "
                    "then enter them."
                    + _name_candidates(
                        path, "missing_quiet_vibrancy"
                    )
                ),
                count=counts["candidates_missing_quiet_vibrancy"],
                command=(
                    "marketsentry list-candidates-needing-scores"
                ),
                severity="action",
            )
        )

    if counts["candidates_failing_gatekeeper"]:
        steps.append(
            RedfinScreeningNextStep(
                step_id="review_noise_risk",
                category="candidate",
                message=(
                    "Candidates failing the Quiet gatekeeper: add "
                    "local noise notes, or hold/reject as a "
                    "noise-risk control."
                    + _name_candidates(
                        path, "failing_gatekeeper"
                    )
                ),
                count=counts["candidates_failing_gatekeeper"],
                command=(
                    "marketsentry candidate-noise-notes "
                    "--candidate-id <id> --noise-risk <level>"
                ),
                severity="warning",
            )
        )

    if counts["candidates_ready_for_decision"]:
        steps.append(
            RedfinScreeningNextStep(
                step_id="decide_candidates",
                category="candidate",
                message=(
                    "Candidates with scores awaiting a decision: "
                    "record save, maybe, hold, or reject."
                ),
                count=counts["candidates_ready_for_decision"],
                command=(
                    "marketsentry candidate-decision "
                    "--candidate-id <id> --decision <decision>"
                ),
                severity="action",
            )
        )

    if counts["watchlist_ready"]:
        steps.append(
            RedfinScreeningNextStep(
                step_id="run_refresh",
                category="watchlist",
                message=(
                    "Watchlist ready: run the local operator "
                    "refresh workflow to update reports."
                ),
                count=counts["watchlist_ready"],
                command=(
                    "marketsentry run-operator-refresh-workflow"
                ),
                severity="info",
            )
        )

    if not steps:
        steps.append(
            RedfinScreeningNextStep(
                step_id="import_screening_urls",
                category="screening",
                message=(
                    "No pending screening work. Import Redfin "
                    "URLs to begin a new screening pass."
                ),
                count=0,
                command=(
                    "marketsentry import-redfin-screening-urls "
                    "--file data/imports/redfin_screening_urls.csv"
                ),
                severity="info",
            )
        )

    return steps


def summarize_screening_operator_status(
    db_path: Optional[str] = None,
    project_root: Optional[str] = None,
) -> RedfinScreeningOperatorStatus:
    """Summarize screening and candidate state with next steps.

    Read-only. Performs no mutation and no live retrieval.

    Args:
        db_path: Path to SQLite database.
        project_root: Root scanned for stray file artifacts.

    Returns:
        Operator status including next steps and warnings.
    """
    path = db_path or config.database_path
    ensure_redfin_screening_queue_schema(db_path=path)

    summary = summarize_redfin_screening_queue(db_path=path)
    counts = _collect_operator_counts(path)

    status = RedfinScreeningOperatorStatus(
        queue=summary,
        saved_missing_enrichment=counts[
            "saved_missing_enrichment"
        ],
        candidates_missing_quiet_vibrancy=counts[
            "candidates_missing_quiet_vibrancy"
        ],
        candidates_failing_gatekeeper=counts[
            "candidates_failing_gatekeeper"
        ],
        candidates_ready_for_decision=counts[
            "candidates_ready_for_decision"
        ],
        watchlist_ready=counts["watchlist_ready"],
        next_steps=build_screening_next_steps(db_path=path),
    )

    if counts["saved_missing_enrichment"]:
        status.warnings.append(
            f"{counts['saved_missing_enrichment']} item(s) saved "
            "for analysis are missing Redfin detail enrichment."
        )
    if counts["candidates_missing_quiet_vibrancy"]:
        status.warnings.append(
            f"{counts['candidates_missing_quiet_vibrancy']} "
            "candidate(s) are missing Quiet/Vibrancy scores."
        )

    # Demo/sample and stray artifact warnings reuse the Milestone
    # 52A detection so the operator sees one consistent answer.
    try:
        from marketsentry.demo_data_cleanup import (
            detect_stray_files,
            identify_demo_records,
        )

        demo_records = identify_demo_records(path)
        if demo_records:
            status.warnings.append(
                f"{len(demo_records)} demo/sample record(s) remain "
                "in the database. Run "
                "'marketsentry cleanup-demo-data' to review."
            )

        strays = [
            s
            for s in detect_stray_files(project_root or ".")
            if s.exists
        ]
        if strays:
            names = ", ".join(s.path for s in strays)
            status.warnings.append(
                f"Stray database/file artifacts detected: {names}."
            )
    except Exception:  # pragma: no cover - defensive
        pass

    return status


# -------------------------------------------------------------------
# Export functions
# -------------------------------------------------------------------


def export_redfin_screening_queue(
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
    fmt: str = "both",
) -> List[str]:
    """Export the screening queue to CSV and/or Markdown.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Path to exports directory.
        fmt: Export format - csv, md, or both.

    Returns:
        List of exported file paths.
    """
    if db_path is None:
        db_path = config.database_path
    if exports_dir is None:
        exports_dir = "data/exports"

    items = list_redfin_screening_items(
        db_path=db_path, limit=10000
    )
    rows = build_screening_report_rows(
        items, db_path=db_path
    )
    next_steps = build_screening_next_steps(db_path=db_path)

    out_path = Path(exports_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"redfin_screening_queue_{ts}"
    paths: List[str] = []

    if fmt in ("md", "both"):
        md_path = out_path / f"{base}.md"
        md_content = _build_screening_md(
            items, rows=rows, next_steps=next_steps
        )
        md_path.write_text(
            md_content, encoding="utf-8"
        )
        paths.append(str(md_path))

    if fmt in ("csv", "both"):
        csv_path = out_path / f"{base}.csv"
        csv_content = _build_screening_csv(items, rows=rows)
        csv_path.write_text(
            csv_content, encoding="utf-8"
        )
        paths.append(str(csv_path))

    return paths


# -------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------


def _update_screening_status(
    screening_id: int,
    new_status: str,
    action: str,
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
) -> RedfinScreeningActionResult:
    """Update screening item status."""
    if db_path is None:
        db_path = config.database_path

    result = RedfinScreeningActionResult(
        screening_id=screening_id,
        action=action,
    )

    ensure_redfin_screening_queue_schema(db_path=db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM redfin_screening_queue "
        "WHERE screening_id = ?",
        (screening_id,),
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        result.detail = (
            f"Screening item {screening_id} not found"
        )
        return result

    # Append notes
    existing_notes = row["user_notes"] or ""
    if notes:
        if existing_notes:
            combined = f"{existing_notes}\n{notes}"
        else:
            combined = notes
    else:
        combined = existing_notes or None

    conn.execute(
        "UPDATE redfin_screening_queue "
        "SET status = ?, "
        "user_screening_decision = ?, "
        "user_notes = ?, "
        "updated_at = CURRENT_TIMESTAMP "
        "WHERE screening_id = ?",
        (new_status, new_status, combined, screening_id),
    )
    conn.commit()
    conn.close()

    result.success = True
    result.detail = (
        f"Item {screening_id} marked as {new_status}"
    )
    return result


def _parse_float(value: str) -> Optional[float]:
    """Parse a float from string, return None if empty."""
    if not value or not value.strip():
        return None
    try:
        cleaned = value.strip().replace(",", "")
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_int(value: str) -> Optional[int]:
    """Parse an int from string, return None if empty."""
    if not value or not value.strip():
        return None
    try:
        cleaned = value.strip().replace(",", "")
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


def _item_next_step(row: RedfinScreeningReportRow) -> str:
    """Derive the next operator step for one screening row."""
    if row.status == "new":
        return "Open Redfin link and visually inspect"
    if row.status == "opened":
        return "Choose Save for Analysis, Hold, or Reject"
    if row.status == "saved_for_analysis":
        if not row.candidate_has_enrichment:
            return (
                "Save Redfin detail HTML and run enrichment"
            )
        if not row.candidate_has_quiet_vibrancy:
            return "Enter Quiet/Vibrancy scores"
        if not row.candidate_watchlisted:
            return "Record a candidate decision"
        return "Watchlisted - run operator refresh workflow"
    if row.status == "hold":
        return "Held for later review"
    if row.status == "rejected":
        return "Rejected - no further action"
    return "Review item status"


def build_screening_report_rows(
    items: List[RedfinScreeningItem],
    db_path: Optional[str] = None,
) -> List[RedfinScreeningReportRow]:
    """Build enriched report rows with candidate status.

    Joins each screening item to its linked candidate so the
    export can show enrichment, scoring, and watchlist state
    alongside the next recommended operator step.

    Args:
        items: Screening items to describe.
        db_path: Path to SQLite database.

    Returns:
        List of enriched report rows.
    """
    path = db_path or config.database_path

    candidate_info: Dict[int, Dict[str, Any]] = {}
    watchlisted_urls: set = set()

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        def _table_exists(name: str) -> bool:
            return cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name=?",
                (name,),
            ).fetchone() is not None

        if _table_exists("candidate_review_queue"):
            for row in cur.execute(
                "SELECT candidate_id, beds, baths, sqft, "
                "quiet_score, vibrancy_score, redfin_url "
                "FROM candidate_review_queue"
            ).fetchall():
                candidate_info[row["candidate_id"]] = {
                    "has_enrichment": any(
                        row[c] is not None
                        for c in ("beds", "baths", "sqft")
                    ),
                    "has_quiet_vibrancy": (
                        row["quiet_score"] is not None
                        and row["vibrancy_score"] is not None
                    ),
                    "redfin_url": row["redfin_url"],
                }

        if _table_exists("watched_properties"):
            for row in cur.execute(
                "SELECT redfin_url FROM watched_properties"
            ).fetchall():
                if row["redfin_url"]:
                    watchlisted_urls.add(row["redfin_url"])
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    rows: List[RedfinScreeningReportRow] = []
    for item in items:
        info = candidate_info.get(item.candidate_id or -1, {})
        row = RedfinScreeningReportRow(
            screening_id=item.screening_id,
            address=item.address,
            city=item.city,
            price=item.price,
            beds=item.beds,
            baths=item.baths,
            sqft=item.sqft,
            quiet_score=item.quiet_score,
            vibrancy_score=item.vibrancy_score,
            status=item.status,
            decision=item.user_screening_decision,
            candidate_id=item.candidate_id,
            redfin_url=item.redfin_url,
            user_notes=item.user_notes,
            saved_for_analysis=(
                item.status == "saved_for_analysis"
            ),
            candidate_has_enrichment=bool(
                info.get("has_enrichment", False)
            ),
            candidate_has_quiet_vibrancy=bool(
                info.get("has_quiet_vibrancy", False)
            ),
            candidate_watchlisted=bool(
                info.get("redfin_url")
                and info["redfin_url"] in watchlisted_urls
            ),
        )
        row.next_step = _item_next_step(row)
        rows.append(row)

    return rows


def _build_screening_md(
    items: List[RedfinScreeningItem],
    rows: Optional[List[RedfinScreeningReportRow]] = None,
    next_steps: Optional[List[RedfinScreeningNextStep]] = None,
) -> str:
    """Build screening queue Markdown report."""
    lines = [
        "# Redfin Screening Queue",
        "",
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total items: {len(items)}",
        "",
    ]

    if next_steps:
        lines.append("## Next Steps")
        lines.append("")
        for step in next_steps:
            suffix = (
                f" ({step.count})" if step.count else ""
            )
            lines.append(f"- {step.message}{suffix}")
            if step.command:
                lines.append(f"  - `{step.command}`")
        lines.append("")

    lines.append("## Screening Items")
    lines.append("")

    if not items:
        lines.append("No screening items found.")
        lines.append("")
        return "\n".join(lines)

    lines.append(
        "| ID | Address | City | Price | "
        "Beds | Baths | SqFt | Status | "
        "Decision | Candidate | Enriched | Scored | "
        "Watchlisted | Next Step | Redfin Link |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|---|"
        "---|---|---|---|---|"
    )

    row_by_id = {r.screening_id: r for r in (rows or [])}

    for item in items:
        price_str = (
            f"${item.price:,.0f}"
            if item.price else ""
        )
        link = (
            f"[View]({item.redfin_url})"
            if item.redfin_url else ""
        )
        cid = (
            str(item.candidate_id)
            if item.candidate_id else ""
        )
        row = row_by_id.get(item.screening_id)
        enriched = (
            "yes"
            if row and row.candidate_has_enrichment
            else "no"
        )
        scored = (
            "yes"
            if row and row.candidate_has_quiet_vibrancy
            else "no"
        )
        watched = (
            "yes"
            if row and row.candidate_watchlisted
            else "no"
        )
        next_step = row.next_step if row else ""
        lines.append(
            f"| {item.screening_id} "
            f"| {item.address or ''} "
            f"| {item.city or ''} "
            f"| {price_str} "
            f"| {item.beds or ''} "
            f"| {item.baths or ''} "
            f"| {item.sqft or ''} "
            f"| {item.status} "
            f"| {item.user_screening_decision} "
            f"| {cid} "
            f"| {enriched} "
            f"| {scored} "
            f"| {watched} "
            f"| {next_step} "
            f"| {link} |"
        )

    lines.append("")
    lines.append("## Safety Note")
    lines.append("")
    lines.append(
        "All operations are local-only. No live "
        "retrieval, no outbound notifications, "
        "no browser automation. Next steps are "
        "data-gathering guidance, not purchase "
        "recommendations."
    )
    lines.append("")

    return "\n".join(lines)


def _build_screening_csv(
    items: List[RedfinScreeningItem],
    rows: Optional[List[RedfinScreeningReportRow]] = None,
) -> str:
    """Build screening queue CSV report."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "screening_id", "address", "city", "price",
        "beds", "baths", "sqft", "quiet_score",
        "vibrancy_score", "status", "decision",
        "candidate_id", "saved_for_analysis",
        "candidate_has_enrichment",
        "candidate_has_quiet_vibrancy",
        "candidate_watchlisted", "next_step",
        "redfin_url", "user_notes",
    ])

    row_by_id = {r.screening_id: r for r in (rows or [])}

    for item in items:
        row = row_by_id.get(item.screening_id)
        writer.writerow([
            item.screening_id,
            item.address or "",
            item.city or "",
            item.price or "",
            item.beds or "",
            item.baths or "",
            item.sqft or "",
            item.quiet_score or "",
            item.vibrancy_score or "",
            item.status,
            item.user_screening_decision,
            item.candidate_id or "",
            "yes" if row and row.saved_for_analysis else "no",
            (
                "yes"
                if row and row.candidate_has_enrichment
                else "no"
            ),
            (
                "yes"
                if row and row.candidate_has_quiet_vibrancy
                else "no"
            ),
            (
                "yes"
                if row and row.candidate_watchlisted
                else "no"
            ),
            row.next_step if row else "",
            item.redfin_url,
            item.user_notes or "",
        ])

    return output.getvalue()
