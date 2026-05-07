"""Retrieved fixture processing pipeline for Market_Sentry.

Processes Redfin HTML fixtures (from live retrieval or manual saves)
through the existing local fixture parsing pipeline. Handles metadata
sidecar JSON files, deduplication via content hashing, fixture capture
queue integration, and processing manifest tracking.

No live retrieval or network calls are performed by this module.
"""

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry import config
from marketsentry.logging_config import logger


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RetrievedFixtureMetadata(BaseModel):
    """Metadata loaded from sidecar JSON for a retrieved fixture."""

    source_url: str = ""
    source_site: str = ""
    request_type: str = ""
    retrieved_at: str = ""
    fixture_path: str = ""
    content_length: int = 0
    retrieval_mode: str = ""
    network_call_performed: bool = False
    audit_record_ref: str = ""


class RetrievedFixtureRecord(BaseModel):
    """A fixture file paired with its optional metadata."""

    fixture_path: str = ""
    metadata_path: str = ""
    metadata: Optional[RetrievedFixtureMetadata] = None
    fixture_type: str = ""  # "search", "property_detail", "unknown"
    content_hash: str = ""
    html_size: int = 0


class RetrievedFixtureProcessingResult(BaseModel):
    """Result of processing a single fixture file."""

    fixture_path: str = ""
    fixture_type: str = ""
    status: str = ""  # "processed", "skipped", "error"
    source_url: str = ""
    candidates_discovered: int = 0
    candidates_inserted: int = 0
    candidates_enriched: int = 0
    listing_events_inserted: int = 0
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    content_hash: str = ""


class RedfinFixtureProcessingRunResult(BaseModel):
    """Overall result of a fixture processing run."""

    search_files_scanned: int = 0
    search_files_processed: int = 0
    detail_files_scanned: int = 0
    detail_files_processed: int = 0
    total_candidates_discovered: int = 0
    total_candidates_inserted: int = 0
    total_duplicates_skipped: int = 0
    total_candidates_enriched: int = 0
    total_listing_events_inserted: int = 0
    total_listing_events_skipped: int = 0
    reports_exported: List[str] = Field(default_factory=list)
    capture_queue_items_marked: int = 0
    manifest_path: str = ""
    fixture_results: List[RetrievedFixtureProcessingResult] = Field(
        default_factory=list
    )
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Metadata loading
# ---------------------------------------------------------------------------


def load_fixture_metadata(
    metadata_path: str,
) -> Optional[RetrievedFixtureMetadata]:
    """Load metadata from a sidecar JSON file.

    Args:
        metadata_path: Path to the JSON metadata file.

    Returns:
        RetrievedFixtureMetadata if file exists and parses, None otherwise.
    """
    path = Path(metadata_path)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return RetrievedFixtureMetadata(**data)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"Failed to parse metadata {metadata_path}: {e}")
        return None


def _compute_content_hash(file_path: str) -> str:
    """Compute SHA-256 hash of file content.

    Args:
        file_path: Path to the file.

    Returns:
        Hex digest string.
    """
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _classify_fixture(filename: str, metadata: Optional[RetrievedFixtureMetadata]) -> str:
    """Classify a fixture as search, property_detail, or unknown.

    Args:
        filename: The fixture filename.
        metadata: Optional metadata with request_type.

    Returns:
        Fixture type string.
    """
    if metadata and metadata.request_type:
        return metadata.request_type

    lower = filename.lower()
    if "search" in lower:
        return "search"
    if "property" in lower or "detail" in lower:
        return "property_detail"
    return "unknown"


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def scan_redfin_fixtures(
    search_dir: Optional[str] = None,
    details_dir: Optional[str] = None,
) -> List[RetrievedFixtureRecord]:
    """Scan directories for Redfin fixture files with optional metadata.

    Args:
        search_dir: Directory for search fixtures.
        details_dir: Directory for detail fixtures.

    Returns:
        List of RetrievedFixtureRecord objects.
    """
    records: List[RetrievedFixtureRecord] = []

    dirs_to_scan = []
    if search_dir:
        dirs_to_scan.append(("search", Path(search_dir)))
    if details_dir:
        dirs_to_scan.append(("property_detail", Path(details_dir)))

    for hint_type, dir_path in dirs_to_scan:
        if not dir_path.exists():
            continue

        for html_file in sorted(dir_path.glob("*.html")):
            metadata_file = html_file.with_suffix(".json")
            metadata = load_fixture_metadata(str(metadata_file))

            fixture_type = _classify_fixture(html_file.name, metadata)
            # Use directory hint if classification returned unknown
            if fixture_type == "unknown":
                fixture_type = hint_type

            content_hash = _compute_content_hash(str(html_file))

            try:
                html_size = html_file.stat().st_size
            except OSError:
                html_size = 0

            records.append(
                RetrievedFixtureRecord(
                    fixture_path=str(html_file),
                    metadata_path=str(metadata_file) if metadata else "",
                    metadata=metadata,
                    fixture_type=fixture_type,
                    content_hash=content_hash,
                    html_size=html_size,
                )
            )

    return records


# ---------------------------------------------------------------------------
# Processing manifest
# ---------------------------------------------------------------------------

MANIFEST_COLUMNS = [
    "processed_at",
    "fixture_path",
    "metadata_path",
    "source_url",
    "fixture_type",
    "status",
    "candidates_discovered",
    "candidates_inserted",
    "candidates_enriched",
    "listing_events_inserted",
    "warnings",
    "errors",
    "content_hash",
]


def _load_manifest_hashes(manifest_path: str) -> set:
    """Load content hashes from existing manifest.

    Args:
        manifest_path: Path to the manifest CSV.

    Returns:
        Set of content hashes that have been successfully processed.
    """
    hashes: set = set()
    path = Path(manifest_path)
    if not path.exists():
        return hashes

    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("status") == "processed" and row.get("content_hash"):
                    hashes.add(row["content_hash"])
    except (OSError, csv.Error):
        pass

    return hashes


def _append_manifest_row(
    manifest_path: str,
    result: RetrievedFixtureProcessingResult,
    metadata_path: str = "",
) -> None:
    """Append a row to the processing manifest.

    Args:
        manifest_path: Path to the manifest CSV.
        result: Processing result for the fixture.
        metadata_path: Path to the metadata JSON file.
    """
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()

    row = {
        "processed_at": datetime.now().isoformat(),
        "fixture_path": result.fixture_path,
        "metadata_path": metadata_path,
        "source_url": result.source_url,
        "fixture_type": result.fixture_type,
        "status": result.status,
        "candidates_discovered": str(result.candidates_discovered),
        "candidates_inserted": str(result.candidates_inserted),
        "candidates_enriched": str(result.candidates_enriched),
        "listing_events_inserted": str(result.listing_events_inserted),
        "warnings": "; ".join(result.warnings) if result.warnings else "",
        "errors": "; ".join(result.errors) if result.errors else "",
        "content_hash": result.content_hash,
    }

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Search fixture processing
# ---------------------------------------------------------------------------


def process_redfin_search_fixtures(
    search_dir: Optional[str] = None,
    database_path: Optional[str] = None,
    force_reprocess: bool = False,
    manifest_path: Optional[str] = None,
) -> RedfinFixtureProcessingRunResult:
    """Process Redfin search fixture HTML files.

    Parses search fixtures using the existing Redfin fixture parser,
    inserts discovered candidates into candidate_review_queue with
    deduplication. No network calls are performed.

    Args:
        search_dir: Directory containing search fixtures.
        database_path: Database path.
        force_reprocess: If True, reprocess even if content hash matches.
        manifest_path: Path to processing manifest CSV.

    Returns:
        RedfinFixtureProcessingRunResult with processing statistics.
    """
    from marketsentry.database import init_db
    from marketsentry.redfin_fixture_parser import parse_redfin_fixtures_from_directory

    db_path = database_path or config.database_path
    search_dir = search_dir or "data/raw/redfin/search"
    manifest = manifest_path or "data/processed/redfin_fixture_processing_manifest.csv"

    result = RedfinFixtureProcessingRunResult(manifest_path=manifest)

    search_path = Path(search_dir)
    if not search_path.exists():
        result.warnings.append(f"Search directory not found: {search_dir}")
        return result

    # Initialize database
    init_db(db_path)

    # Scan fixtures
    records = scan_redfin_fixtures(search_dir=search_dir)
    search_records = [r for r in records if r.fixture_type == "search"]
    result.search_files_scanned = len(search_records)

    if not search_records:
        result.warnings.append("No search fixtures found.")
        return result

    # Load manifest for skip logic
    processed_hashes = set() if force_reprocess else _load_manifest_hashes(manifest)

    # Process each fixture
    for record in search_records:
        proc_result = RetrievedFixtureProcessingResult(
            fixture_path=record.fixture_path,
            fixture_type=record.fixture_type,
            source_url=record.metadata.source_url if record.metadata else "",
            content_hash=record.content_hash,
        )

        # Skip if already processed
        if record.content_hash in processed_hashes:
            proc_result.status = "skipped"
            result.fixture_results.append(proc_result)
            continue

        try:
            # Parse using existing parser
            discovery = parse_redfin_fixtures_from_directory(
                directory_path=str(Path(record.fixture_path).parent),
                database_path=db_path,
                record_source_pages=True,
            )

            proc_result.status = "processed"
            proc_result.candidates_discovered = discovery.total_rows_read
            proc_result.candidates_inserted = discovery.candidates_inserted

            result.search_files_processed += 1
            result.total_candidates_discovered += discovery.total_rows_read
            result.total_candidates_inserted += discovery.candidates_inserted
            result.total_duplicates_skipped += discovery.candidates_skipped

            if discovery.parse_warnings:
                proc_result.warnings.append(
                    f"{discovery.parse_warnings} parse warning(s)"
                )
            if discovery.parse_errors:
                proc_result.errors.append(
                    f"{discovery.parse_errors} parse error(s)"
                )

        except Exception as e:
            proc_result.status = "error"
            proc_result.errors.append(f"{type(e).__name__}: {e}")
            result.errors.append(f"Error processing {record.fixture_path}: {e}")

        result.fixture_results.append(proc_result)
        _append_manifest_row(manifest, proc_result, record.metadata_path)

    return result


# ---------------------------------------------------------------------------
# Detail fixture processing
# ---------------------------------------------------------------------------


def process_redfin_detail_fixtures(
    details_dir: Optional[str] = None,
    database_path: Optional[str] = None,
    force_reprocess: bool = False,
    manifest_path: Optional[str] = None,
) -> RedfinFixtureProcessingRunResult:
    """Process Redfin detail fixture HTML files.

    Parses detail fixtures using the existing Redfin detail parser
    and enrichment workflow. Enriches candidate_review_queue and inserts
    listing events. No network calls are performed.

    Args:
        details_dir: Directory containing detail fixtures.
        database_path: Database path.
        force_reprocess: If True, reprocess even if content hash matches.
        manifest_path: Path to processing manifest CSV.

    Returns:
        RedfinFixtureProcessingRunResult with processing statistics.
    """
    from marketsentry.database import init_db
    from marketsentry.redfin_detail_enrichment import (
        enrich_candidates_from_detail_directory,
    )

    db_path = database_path or config.database_path
    details_dir = details_dir or "data/raw/redfin/details"
    manifest = manifest_path or "data/processed/redfin_fixture_processing_manifest.csv"

    result = RedfinFixtureProcessingRunResult(manifest_path=manifest)

    details_path = Path(details_dir)
    if not details_path.exists():
        result.warnings.append(f"Details directory not found: {details_dir}")
        return result

    # Initialize database
    init_db(db_path)

    # Scan fixtures
    records = scan_redfin_fixtures(details_dir=details_dir)
    detail_records = [r for r in records if r.fixture_type == "property_detail"]
    result.detail_files_scanned = len(detail_records)

    if not detail_records:
        result.warnings.append("No detail fixtures found.")
        return result

    # Load manifest for skip logic
    processed_hashes = set() if force_reprocess else _load_manifest_hashes(manifest)

    # Check if all files already processed
    unprocessed = [r for r in detail_records if r.content_hash not in processed_hashes]

    if not unprocessed:
        for record in detail_records:
            proc_result = RetrievedFixtureProcessingResult(
                fixture_path=record.fixture_path,
                fixture_type=record.fixture_type,
                source_url=record.metadata.source_url if record.metadata else "",
                content_hash=record.content_hash,
                status="skipped",
            )
            result.fixture_results.append(proc_result)
        return result

    try:
        # Enrich using existing enrichment pipeline
        enrichment = enrich_candidates_from_detail_directory(
            directory_path=details_dir,
            database_path=db_path,
        )

        result.detail_files_processed = enrichment.total_files_processed
        result.total_candidates_enriched = enrichment.candidates_updated
        result.total_listing_events_inserted = enrichment.listing_events_inserted
        result.total_listing_events_skipped = enrichment.listing_events_skipped

        if enrichment.parse_warnings:
            result.warnings.append(
                f"{enrichment.parse_warnings} detail parse warning(s)"
            )
        if enrichment.parse_errors:
            result.errors.append(
                f"{enrichment.parse_errors} detail parse error(s)"
            )

        # Record each fixture
        for record in detail_records:
            proc_result = RetrievedFixtureProcessingResult(
                fixture_path=record.fixture_path,
                fixture_type=record.fixture_type,
                source_url=record.metadata.source_url if record.metadata else "",
                content_hash=record.content_hash,
            )
            if record.content_hash in processed_hashes:
                proc_result.status = "skipped"
            else:
                proc_result.status = "processed"
                # Distribute enrichment counts across fixtures proportionally
                if enrichment.total_files_processed > 0:
                    proc_result.candidates_enriched = (
                        enrichment.candidates_updated // enrichment.total_files_processed
                    )
                    proc_result.listing_events_inserted = (
                        enrichment.listing_events_inserted // enrichment.total_files_processed
                    )

            result.fixture_results.append(proc_result)
            if proc_result.status != "skipped":
                _append_manifest_row(manifest, proc_result, record.metadata_path)

    except Exception as e:
        result.errors.append(f"Error processing detail fixtures: {e}")
        for record in unprocessed:
            proc_result = RetrievedFixtureProcessingResult(
                fixture_path=record.fixture_path,
                fixture_type=record.fixture_type,
                source_url=record.metadata.source_url if record.metadata else "",
                content_hash=record.content_hash,
                status="error",
                errors=[f"{type(e).__name__}: {e}"],
            )
            result.fixture_results.append(proc_result)

    return result


# ---------------------------------------------------------------------------
# Fixture capture queue integration
# ---------------------------------------------------------------------------


def _mark_matching_capture_requests(
    fixture_results: List[RetrievedFixtureProcessingResult],
    database_path: Optional[str] = None,
) -> int:
    """Mark fixture capture queue items as captured when processed.

    If a processed fixture's source_url matches a pending capture queue
    request, mark it as captured.

    Args:
        fixture_results: List of processing results.
        database_path: Database path.

    Returns:
        Number of capture queue items marked.
    """
    from marketsentry.fixture_capture_queue import (
        list_pending_capture_requests,
        mark_fixture_captured,
    )

    db_path = database_path or config.database_path
    marked = 0

    try:
        pending = list_pending_capture_requests(
            source_site="redfin", database_path=db_path
        )
    except Exception:
        return 0

    if not pending:
        return 0

    # Build URL-to-request-id mapping
    url_to_id: Dict[str, int] = {}
    for req in pending:
        url = req.get("source_url", "") or req.get("normalized_url", "")
        req_id = req.get("capture_request_id")
        if url and req_id:
            url_to_id[url] = req_id

    for result in fixture_results:
        if result.status != "processed" or not result.source_url:
            continue

        if result.source_url in url_to_id:
            req_id = url_to_id[result.source_url]
            try:
                success = mark_fixture_captured(
                    capture_request_id=req_id,
                    fixture_path=result.fixture_path,
                    database_path=db_path,
                )
                if success:
                    marked += 1
            except Exception as e:
                logger.warning(f"Failed to mark capture request {req_id}: {e}")

    return marked


# ---------------------------------------------------------------------------
# Integrated processing workflow
# ---------------------------------------------------------------------------


def process_redfin_retrieved_fixtures(
    search_dir: Optional[str] = None,
    details_dir: Optional[str] = None,
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    force_reprocess: bool = False,
    manifest_path: Optional[str] = None,
) -> RedfinFixtureProcessingRunResult:
    """Integrated Redfin fixture processing workflow.

    Steps:
    1. Process Redfin search fixtures (insert candidates).
    2. Process Redfin detail fixtures (enrich candidates).
    3. Recalculate candidate metrics (Effective DOM, scoring).
    4. Persist Effective DOM v2.
    5. Export candidate review CSV.
    6. Export candidate analysis report.
    7. Mark matching fixture capture queue items as captured.
    8. Return structured run result.

    No live retrieval is performed by this function.

    Args:
        search_dir: Directory for search fixtures.
        details_dir: Directory for detail fixtures.
        database_path: Database path.
        output_dir: Output directory for reports.
        force_reprocess: If True, reprocess all fixtures.
        manifest_path: Path to processing manifest CSV.

    Returns:
        RedfinFixtureProcessingRunResult with full statistics.
    """
    from marketsentry.candidate_recalc import recalculate_candidates
    from marketsentry.candidate_report import export_candidate_analysis_report
    from marketsentry.database import init_db
    from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2
    from marketsentry.review_export import export_candidates_from_db

    db_path = database_path or config.database_path
    search_dir = search_dir or "data/raw/redfin/search"
    details_dir = details_dir or "data/raw/redfin/details"
    output_dir = output_dir or "data/exports"
    manifest = manifest_path or "data/processed/redfin_fixture_processing_manifest.csv"

    # Initialize database
    init_db(db_path)

    result = RedfinFixtureProcessingRunResult(manifest_path=manifest)

    # Step 1: Process search fixtures
    logger.info("Step 1: Processing Redfin search fixtures...")
    search_result = process_redfin_search_fixtures(
        search_dir=search_dir,
        database_path=db_path,
        force_reprocess=force_reprocess,
        manifest_path=manifest,
    )
    result.search_files_scanned = search_result.search_files_scanned
    result.search_files_processed = search_result.search_files_processed
    result.total_candidates_discovered = search_result.total_candidates_discovered
    result.total_candidates_inserted = search_result.total_candidates_inserted
    result.total_duplicates_skipped = search_result.total_duplicates_skipped
    result.fixture_results.extend(search_result.fixture_results)
    result.warnings.extend(search_result.warnings)
    result.errors.extend(search_result.errors)

    # Step 2: Process detail fixtures
    logger.info("Step 2: Processing Redfin detail fixtures...")
    detail_result = process_redfin_detail_fixtures(
        details_dir=details_dir,
        database_path=db_path,
        force_reprocess=force_reprocess,
        manifest_path=manifest,
    )
    result.detail_files_scanned = detail_result.detail_files_scanned
    result.detail_files_processed = detail_result.detail_files_processed
    result.total_candidates_enriched = detail_result.total_candidates_enriched
    result.total_listing_events_inserted = detail_result.total_listing_events_inserted
    result.total_listing_events_skipped = detail_result.total_listing_events_skipped
    result.fixture_results.extend(detail_result.fixture_results)
    result.warnings.extend(detail_result.warnings)
    result.errors.extend(detail_result.errors)

    # Step 3: Recalculate candidates
    logger.info("Step 3: Recalculating candidate metrics...")
    try:
        recalc = recalculate_candidates(database_path=db_path)
        logger.info(
            f"  Recalc: {recalc.candidates_scanned} scanned, "
            f"{recalc.candidates_updated} updated"
        )
    except Exception as e:
        result.errors.append(f"Recalculation error: {e}")

    # Step 4: Persist Effective DOM v2
    logger.info("Step 4: Persisting Effective DOM v2...")
    try:
        persist_effective_dom_v2(database_path=db_path)
    except Exception as e:
        result.warnings.append(f"Effective DOM v2 persistence warning: {e}")

    # Step 5: Export candidate review CSV
    logger.info("Step 5: Exporting candidate review CSV...")
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        review_path = str(Path(output_dir) / f"candidate_review_{ts}.csv")
        exported_review = export_candidates_from_db(
            output_file=review_path, database_path=db_path
        )
        result.reports_exported.append(exported_review)
    except Exception as e:
        result.warnings.append(f"Review export warning: {e}")

    # Step 6: Export candidate analysis report
    logger.info("Step 6: Exporting candidate analysis report...")
    try:
        analysis_path = str(Path(output_dir) / f"candidate_analysis_{ts}.csv")
        exported_analysis = export_candidate_analysis_report(
            database_path=db_path, output_path=analysis_path
        )
        result.reports_exported.append(exported_analysis)
    except Exception as e:
        result.warnings.append(f"Analysis export warning: {e}")

    # Step 7: Mark capture queue items
    logger.info("Step 7: Checking fixture capture queue...")
    try:
        marked = _mark_matching_capture_requests(
            fixture_results=result.fixture_results,
            database_path=db_path,
        )
        result.capture_queue_items_marked = marked
    except Exception as e:
        result.warnings.append(f"Capture queue integration warning: {e}")

    logger.info(
        f"Processing complete: "
        f"{result.search_files_processed} search, "
        f"{result.detail_files_processed} detail fixtures processed."
    )

    return result
