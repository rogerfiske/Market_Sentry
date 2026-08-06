"""Safe demo/sample data cleanup and stray artifact detection.

The operator console becomes noisy when demo/sample records seeded for
testing remain alongside real user properties. This module identifies
those records by unmistakable marker addresses and offers an explicit,
dry-run-by-default cleanup.

Safety model:

- Dry-run is the default. Nothing mutates without an explicit confirm.
- Only records matching a fixed allowlist of demo marker addresses are
  ever selected.
- Real user addresses are protected by an explicit denylist that is
  checked a second time immediately before any deletion.
- Stray file artifacts are reported but never deleted without a
  separate explicit flag.

This module does NOT perform live retrieval, browser automation,
outbound notifications, or credential storage. It does not modify the
Quiet Score gatekeeper and does not add walkability fields.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.config import config
from marketsentry.logging_config import logger

# Unmistakable demo/sample marker addresses seeded by sample_data.py.
SEEDED_SAMPLE_ADDRESSES: List[str] = [
    "12345 Sample St",
    "67890 Busy Ave",
    "11111 Unknown Rd",
]

# Unmistakable demo/sample marker addresses used for screening-queue
# validation during Milestone 52.
SCREENING_DEMO_ADDRESSES: List[str] = [
    "40000 Example St",
    "30000 Sample Ave",
    "55555 Fixture Ln",
]

DEMO_MARKER_ADDRESSES: List[str] = (
    SEEDED_SAMPLE_ADDRESSES + SCREENING_DEMO_ADDRESSES
)

# Real operator properties. These must never be selected for removal.
# Checked again immediately before deletion as a second guard.
PROTECTED_ADDRESSES: List[str] = [
    "31801 Valone Ct",
    "31457 Britton Cir",
    "41451 Royal Dornoch Ct",
    "32420 San Marco Dr",
    "32152 Camino Nunez",
]

# Stray file artifacts with their likely cause. Reported, never deleted
# without an explicit confirm flag.
STRAY_FILE_CANDIDATES: List[Dict[str, str]] = [
    {
        "path": "nul",
        "kind": "windows_redirect_artifact",
        "explanation": (
            "Created when a Windows-style '2>nul' redirect runs under a "
            "POSIX shell (Git Bash). Safe to delete."
        ),
    },
    {
        "path": "dbmarketsentry.db",
        "kind": "shell_quoting_artifact",
        "explanation": (
            "Created by '--db db\\marketsentry.db' where the backslash was "
            "consumed as an escape character. Safe to delete if empty of "
            "real data."
        ),
    },
    {
        "path": "data/market_sentry.db",
        "kind": "legacy_wrong_default",
        "explanation": (
            "Created by the pre-Milestone-52A wrong default path. The "
            "canonical database is db/marketsentry.db. Safe to delete if "
            "empty of real data."
        ),
    },
]


class DemoDataRecord(BaseModel):
    """A single demo/sample record identified for cleanup."""

    table_name: str = Field(description="Source table name")
    record_id: int = Field(description="Primary key of the record")
    address: Optional[str] = Field(
        default=None, description="Address on the record"
    )
    category: str = Field(
        description="seeded_sample or screening_demo"
    )
    detail: str = Field(
        default="", description="Why this record was selected"
    )
    linked_candidate_id: Optional[int] = Field(
        default=None,
        description="Candidate linked from a screening item",
    )


class StrayFileArtifact(BaseModel):
    """A stray file artifact detected in the project root."""

    path: str = Field(description="Relative path to the artifact")
    kind: str = Field(description="Artifact classification")
    explanation: str = Field(description="Likely cause and guidance")
    size_bytes: int = Field(default=0, description="File size on disk")
    exists: bool = Field(default=False, description="Present on disk")


class DemoDataCleanupPlan(BaseModel):
    """Planned cleanup actions. Building a plan never mutates state."""

    db_path: str = Field(description="Database inspected")
    project_root: str = Field(description="Project root inspected")
    demo_records: List[DemoDataRecord] = Field(default_factory=list)
    stray_files: List[StrayFileArtifact] = Field(default_factory=list)
    protected_addresses: List[str] = Field(
        default_factory=lambda: list(PROTECTED_ADDRESSES)
    )
    protected_records_found: int = Field(
        default=0,
        description="Real records seen and deliberately left alone",
    )
    notes: List[str] = Field(default_factory=list)

    @property
    def demo_record_count(self) -> int:
        """Total demo records selected for cleanup."""
        return len(self.demo_records)

    @property
    def stray_file_count(self) -> int:
        """Total stray files detected on disk."""
        return len([s for s in self.stray_files if s.exists])


class DemoDataCleanupResult(BaseModel):
    """Outcome of an executed cleanup."""

    dry_run: bool = Field(description="True when nothing was mutated")
    db_path: str = Field(description="Database targeted")
    removed_records: List[DemoDataRecord] = Field(default_factory=list)
    removed_files: List[str] = Field(default_factory=list)
    skipped_protected: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)

    @property
    def removed_record_count(self) -> int:
        """Number of database records removed."""
        return len(self.removed_records)

    @property
    def removed_file_count(self) -> int:
        """Number of stray files removed."""
        return len(self.removed_files)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check whether a table exists in the connected database."""
    row = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def is_protected_address(address: Optional[str]) -> bool:
    """Return True when an address belongs to a real user property.

    Matching is substring-based and case-insensitive because stored
    addresses sometimes carry appended city/state/ZIP text.
    """
    if not address:
        return False
    lowered = address.lower()
    return any(p.lower() in lowered for p in PROTECTED_ADDRESSES)


def is_demo_address(address: Optional[str]) -> bool:
    """Return True when an address matches a known demo marker."""
    if not address:
        return False
    lowered = address.lower()
    if is_protected_address(address):
        return False
    return any(m.lower() in lowered for m in DEMO_MARKER_ADDRESSES)


def _category_for(address: str) -> str:
    """Classify a demo address as seeded_sample or screening_demo."""
    lowered = address.lower()
    for marker in SCREENING_DEMO_ADDRESSES:
        if marker.lower() in lowered:
            return "screening_demo"
    return "seeded_sample"


def identify_demo_records(
    db_path: Optional[str] = None,
) -> List[DemoDataRecord]:
    """Identify demo/sample records without mutating anything.

    Args:
        db_path: Database to inspect. Defaults to the canonical
            project database from config.

    Returns:
        List of demo records across screening, candidate, and
        watchlist tables. Real user records are never included.
    """
    path = db_path or config.database_path
    records: List[DemoDataRecord] = []

    if not Path(path).exists():
        return records

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        if _table_exists(conn, "redfin_screening_queue"):
            rows = conn.execute(
                "SELECT screening_id, address, candidate_id "
                "FROM redfin_screening_queue"
            ).fetchall()
            for row in rows:
                if not is_demo_address(row["address"]):
                    continue
                records.append(
                    DemoDataRecord(
                        table_name="redfin_screening_queue",
                        record_id=row["screening_id"],
                        address=row["address"],
                        category=_category_for(row["address"]),
                        detail="Demo screening-queue item",
                        linked_candidate_id=row["candidate_id"],
                    )
                )

        if _table_exists(conn, "candidate_review_queue"):
            rows = conn.execute(
                "SELECT candidate_id, address "
                "FROM candidate_review_queue"
            ).fetchall()
            for row in rows:
                if not is_demo_address(row["address"]):
                    continue
                records.append(
                    DemoDataRecord(
                        table_name="candidate_review_queue",
                        record_id=row["candidate_id"],
                        address=row["address"],
                        category=_category_for(row["address"]),
                        detail="Demo candidate record",
                    )
                )

        if _table_exists(conn, "watched_properties"):
            rows = conn.execute(
                "SELECT property_id, address FROM watched_properties"
            ).fetchall()
            for row in rows:
                if not is_demo_address(row["address"]):
                    continue
                records.append(
                    DemoDataRecord(
                        table_name="watched_properties",
                        record_id=row["property_id"],
                        address=row["address"],
                        category=_category_for(row["address"]),
                        detail="Demo watched property",
                    )
                )
    finally:
        conn.close()

    return records


def count_protected_records(db_path: Optional[str] = None) -> int:
    """Count real user records that will deliberately be left alone."""
    path = db_path or config.database_path
    if not Path(path).exists():
        return 0

    total = 0
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        table_columns = [
            ("redfin_screening_queue", "address"),
            ("candidate_review_queue", "address"),
            ("watched_properties", "address"),
        ]
        for table, column in table_columns:
            if not _table_exists(conn, table):
                continue
            rows = conn.execute(
                f"SELECT {column} FROM {table}"  # noqa: S608
            ).fetchall()
            total += sum(
                1 for r in rows if is_protected_address(r[column])
            )
    finally:
        conn.close()

    return total


def _entry_in_listing(target: Path) -> bool:
    """Check a directory listing for an exact filename.

    Path.is_file() cannot be used for Windows reserved names such as
    'nul': that path resolves to the NUL character device, so is_file()
    returns False even when a real stray file of that name exists, and
    exists() returns True even when it does not. The parent directory
    listing is the only reliable test for both cases.
    """
    parent = target.parent if str(target.parent) else Path(".")
    try:
        return target.name in os.listdir(parent)
    except OSError:
        return False


def _safe_size(target: Path) -> int:
    """Return a file size, tolerating unstattable reserved names."""
    try:
        return target.stat().st_size
    except OSError:
        return 0


def detect_stray_files(
    project_root: Optional[str] = None,
) -> List[StrayFileArtifact]:
    """Detect known stray file artifacts. Never deletes anything."""
    root = Path(project_root or ".")
    artifacts: List[StrayFileArtifact] = []

    for spec in STRAY_FILE_CANDIDATES:
        target = root / spec["path"]
        exists = _entry_in_listing(target)
        size = _safe_size(target) if exists else 0
        artifacts.append(
            StrayFileArtifact(
                path=spec["path"],
                kind=spec["kind"],
                explanation=spec["explanation"],
                size_bytes=size,
                exists=exists,
            )
        )

    return artifacts


def _remove_stray_file(target: Path) -> None:
    """Delete a stray file, handling Windows reserved names.

    A file literally named 'nul' cannot be removed through its normal
    path because that resolves to the NUL device. The extended-length
    '\\\\?\\' prefix bypasses reserved-name parsing.
    """
    try:
        os.remove(target)
        return
    except OSError:
        if os.name != "nt":
            raise

    extended = "\\\\?\\" + str(target.resolve())
    os.remove(extended)


def build_cleanup_plan(
    db_path: Optional[str] = None,
    project_root: Optional[str] = None,
) -> DemoDataCleanupPlan:
    """Build a cleanup plan. Read-only; never mutates state."""
    path = db_path or config.database_path
    root = project_root or "."

    demo_records = identify_demo_records(path)
    stray_files = detect_stray_files(root)
    protected_found = count_protected_records(path)

    notes: List[str] = [
        "Dry-run by default. Nothing is removed without --confirm.",
        "Real user properties are never selected for removal.",
        "Stray files require --confirm-stray-files to delete.",
    ]
    if not Path(path).exists():
        notes.append(f"Database not found at {path}.")

    return DemoDataCleanupPlan(
        db_path=path,
        project_root=str(root),
        demo_records=demo_records,
        stray_files=stray_files,
        protected_records_found=protected_found,
        notes=notes,
    )


def execute_cleanup(
    plan: DemoDataCleanupPlan,
    confirm: bool = False,
    confirm_stray_files: bool = False,
) -> DemoDataCleanupResult:
    """Execute a cleanup plan.

    Args:
        plan: Plan produced by build_cleanup_plan.
        confirm: Must be True to remove database records.
        confirm_stray_files: Must be True to delete stray files.

    Returns:
        Result describing exactly what was removed or would be removed.
    """
    result = DemoDataCleanupResult(
        dry_run=not confirm,
        db_path=plan.db_path,
    )

    # Second guard: re-check the protected denylist immediately before
    # any deletion, independent of how the plan was built.
    safe_records: List[DemoDataRecord] = []
    for record in plan.demo_records:
        if is_protected_address(record.address):
            result.skipped_protected.append(
                f"{record.table_name}#{record.record_id} "
                f"({record.address})"
            )
            continue
        safe_records.append(record)

    if not confirm:
        for record in safe_records:
            result.actions.append(
                f"WOULD REMOVE {record.table_name}"
                f"#{record.record_id} ({record.address})"
            )
        for stray in plan.stray_files:
            if stray.exists:
                result.actions.append(
                    f"WOULD REMOVE FILE {stray.path} "
                    f"({stray.size_bytes} bytes)"
                )
        return result

    if not Path(plan.db_path).exists():
        result.actions.append(
            f"Database not found at {plan.db_path}; no records removed."
        )
    else:
        table_keys = {
            "redfin_screening_queue": "screening_id",
            "candidate_review_queue": "candidate_id",
            "watched_properties": "property_id",
        }
        conn = sqlite3.connect(plan.db_path)
        try:
            # Delete screening items first so linked candidate rows do
            # not leave dangling references behind.
            ordered = sorted(
                safe_records,
                key=lambda r: 0
                if r.table_name == "redfin_screening_queue"
                else 1,
            )
            for record in ordered:
                key = table_keys.get(record.table_name)
                if key is None:
                    continue
                if not _table_exists(conn, record.table_name):
                    continue
                conn.execute(
                    f"DELETE FROM {record.table_name} "  # noqa: S608
                    f"WHERE {key} = ?",
                    (record.record_id,),
                )
                result.removed_records.append(record)
                result.actions.append(
                    f"REMOVED {record.table_name}"
                    f"#{record.record_id} ({record.address})"
                )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Demo data cleanup removed %d records from %s",
            len(result.removed_records),
            plan.db_path,
        )

    if confirm_stray_files:
        root = Path(plan.project_root)
        for stray in plan.stray_files:
            if not stray.exists:
                continue
            target = root / stray.path
            try:
                _remove_stray_file(target)
                result.removed_files.append(stray.path)
                result.actions.append(f"REMOVED FILE {stray.path}")
            except OSError as exc:
                result.actions.append(
                    f"COULD NOT REMOVE FILE {stray.path}: {exc}"
                )
    else:
        for stray in plan.stray_files:
            if stray.exists:
                result.actions.append(
                    f"DETECTED STRAY FILE {stray.path} "
                    "(use --confirm-stray-files to delete)"
                )

    return result


def summarize_cleanup_plan(plan: DemoDataCleanupPlan) -> Dict[str, Any]:
    """Summarize a plan for display or export."""
    by_category: Dict[str, int] = {}
    by_table: Dict[str, int] = {}
    for record in plan.demo_records:
        by_category[record.category] = (
            by_category.get(record.category, 0) + 1
        )
        by_table[record.table_name] = (
            by_table.get(record.table_name, 0) + 1
        )

    return {
        "db_path": plan.db_path,
        "demo_record_count": plan.demo_record_count,
        "stray_file_count": plan.stray_file_count,
        "protected_records_found": plan.protected_records_found,
        "by_category": by_category,
        "by_table": by_table,
    }
