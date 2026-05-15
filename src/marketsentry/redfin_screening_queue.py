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
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
        db_path = "db/marketsentry.db"

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
        db_path = "db/marketsentry.db"

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
        db_path = "db/marketsentry.db"

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
        db_path = "db/marketsentry.db"

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
        db_path = "db/marketsentry.db"

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
        db_path = "db/marketsentry.db"

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
        db_path = "db/marketsentry.db"

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
        db_path = "db/marketsentry.db"
    if exports_dir is None:
        exports_dir = "data/exports"

    items = list_redfin_screening_items(
        db_path=db_path, limit=10000
    )

    out_path = Path(exports_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"redfin_screening_queue_{ts}"
    paths: List[str] = []

    if fmt in ("md", "both"):
        md_path = out_path / f"{base}.md"
        md_content = _build_screening_md(items)
        md_path.write_text(
            md_content, encoding="utf-8"
        )
        paths.append(str(md_path))

    if fmt in ("csv", "both"):
        csv_path = out_path / f"{base}.csv"
        csv_content = _build_screening_csv(items)
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
        db_path = "db/marketsentry.db"

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


def _build_screening_md(
    items: List[RedfinScreeningItem],
) -> str:
    """Build screening queue Markdown report."""
    lines = [
        "# Redfin Screening Queue",
        "",
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total items: {len(items)}",
        "",
        "## Screening Items",
        "",
    ]

    if not items:
        lines.append("No screening items found.")
        lines.append("")
        return "\n".join(lines)

    lines.append(
        "| ID | Address | City | Price | "
        "Beds | Baths | SqFt | Status | "
        "Decision | Candidate | Redfin Link |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|---|---|"
    )

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
            f"| {link} |"
        )

    lines.append("")
    lines.append("## Safety Note")
    lines.append("")
    lines.append(
        "All operations are local-only. No live "
        "retrieval, no outbound notifications, "
        "no browser automation."
    )
    lines.append("")

    return "\n".join(lines)


def _build_screening_csv(
    items: List[RedfinScreeningItem],
) -> str:
    """Build screening queue CSV report."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "screening_id", "address", "city", "price",
        "beds", "baths", "sqft", "quiet_score",
        "vibrancy_score", "status", "decision",
        "candidate_id", "redfin_url", "user_notes",
    ])

    for item in items:
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
            item.redfin_url,
            item.user_notes or "",
        ])

    return output.getvalue()
