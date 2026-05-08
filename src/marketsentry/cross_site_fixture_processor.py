"""Cross-site fixture processor for manual HTML fixtures.

Processes saved HTML fixtures from Zillow, Realtor.com, Homes.com, and
Compass. Uses existing source-specific parsers from Milestone 6. Writes
an append-only processing manifest and integrates with the fixture capture
queue.

No network calls are performed. No live retrieval.
"""

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.logging_config import logger
from marketsentry.models import CrossSiteParseResult


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CrossSiteFixtureMetadata(BaseModel):
    """Metadata about a cross-site fixture file."""

    fixture_path: str = ""
    source_site: str = ""
    fixture_type: str = "property_detail"
    content_hash: str = ""
    content_length: int = 0
    source_url: str = ""


class CrossSiteFixtureRecord(BaseModel):
    """A cross-site fixture file record for processing."""

    fixture_path: str = ""
    source_site: str = ""
    fixture_type: str = "property_detail"
    content_hash: str = ""
    content_length: int = 0
    already_processed: bool = False


class CrossSiteFixtureProcessingResult(BaseModel):
    """Result of processing a single cross-site fixture."""

    fixture_path: str = ""
    source_site: str = ""
    fixture_type: str = ""
    status: str = ""  # processed, skipped, failed
    observations_inserted: int = 0
    candidates_matched: int = 0
    watched_properties_matched: int = 0
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    content_hash: str = ""
    source_url: str = ""


class CrossSiteFixtureProcessingRunResult(BaseModel):
    """Result of a full cross-site fixture processing run."""

    files_scanned: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    observations_inserted: int = 0
    candidates_matched: int = 0
    watched_properties_matched: int = 0
    duplicates_skipped: int = 0
    queue_items_marked_captured: int = 0
    warnings: int = 0
    errors: int = 0
    results: List[CrossSiteFixtureProcessingResult] = Field(default_factory=list)
    sources_processed: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser mapping
# ---------------------------------------------------------------------------

SUPPORTED_SOURCES = ["zillow", "realtor", "homes", "compass"]

# Directories where fixtures are expected
SOURCE_FIXTURE_DIRS = {
    "zillow": "data/raw/zillow/details",
    "realtor": "data/raw/realtor/details",
    "homes": "data/raw/homes/details",
    "compass": "data/raw/compass/details",
}

# Legacy directories (from Milestone 6) also checked
LEGACY_FIXTURE_DIRS = {
    "zillow": "data/raw/cross_site/zillow",
    "realtor": "data/raw/cross_site/realtor",
    "homes": "data/raw/cross_site/homes",
    "compass": "data/raw/cross_site/compass",
}

MANIFEST_FILENAME = "cross_site_fixture_processing_manifest.csv"

MANIFEST_FIELDNAMES = [
    "processed_at", "source_site", "fixture_path", "source_url",
    "fixture_type", "status", "observations_inserted",
    "candidates_matched", "watched_properties_matched",
    "warnings", "errors", "content_hash",
]


def _get_parser(source_site: str) -> Optional[Callable]:
    """Get the parser function for a source site.

    Args:
        source_site: Source site name.

    Returns:
        Parser function or None.
    """
    if source_site == "zillow":
        from marketsentry.zillow_parser import parse_zillow_detail_file
        return parse_zillow_detail_file
    elif source_site == "realtor":
        from marketsentry.realtor_parser import parse_realtor_detail_file
        return parse_realtor_detail_file
    elif source_site == "homes":
        from marketsentry.homes_parser import parse_homes_detail_file
        return parse_homes_detail_file
    elif source_site == "compass":
        from marketsentry.compass_parser import parse_compass_detail_file
        return parse_compass_detail_file
    return None


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def load_cross_site_fixture_metadata(
    fixture_path: str,
    source_site: str,
) -> CrossSiteFixtureMetadata:
    """Load metadata for a cross-site fixture file.

    Args:
        fixture_path: Path to the HTML fixture.
        source_site: Source site name.

    Returns:
        CrossSiteFixtureMetadata with file info and content hash.
    """
    fpath = Path(fixture_path)
    content = ""
    if fpath.exists():
        content = fpath.read_text(encoding="utf-8", errors="replace")

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    return CrossSiteFixtureMetadata(
        fixture_path=str(fpath),
        source_site=source_site,
        fixture_type="property_detail",
        content_hash=content_hash,
        content_length=len(content),
    )


def scan_cross_site_fixtures(
    root_dir: Optional[str] = None,
    source_site: Optional[str] = None,
    fixture_dir: Optional[str] = None,
) -> List[CrossSiteFixtureRecord]:
    """Scan directories for cross-site HTML fixture files.

    Args:
        root_dir: Root data directory (default: 'data/raw').
        source_site: If provided, scan only this source.
        fixture_dir: If provided, scan this directory directly.

    Returns:
        List of CrossSiteFixtureRecord for found HTML files.
    """
    records: List[CrossSiteFixtureRecord] = []

    if fixture_dir:
        # Scan a specific directory
        src = source_site or "unknown"
        _scan_directory(Path(fixture_dir), src, records)
        return records

    sources = [source_site] if source_site else SUPPORTED_SOURCES

    for src in sources:
        # Check primary directory
        primary_dir = SOURCE_FIXTURE_DIRS.get(src, "")
        if root_dir:
            # Adapt path relative to custom root
            primary_dir = str(Path(root_dir) / src / "details")

        if primary_dir:
            _scan_directory(Path(primary_dir), src, records)

        # Check legacy directory
        if not root_dir:
            legacy_dir = LEGACY_FIXTURE_DIRS.get(src, "")
            if legacy_dir:
                _scan_directory(Path(legacy_dir), src, records)

    return records


def _scan_directory(
    dir_path: Path,
    source_site: str,
    records: List[CrossSiteFixtureRecord],
) -> None:
    """Scan a directory for HTML files and add to records list.

    Args:
        dir_path: Directory to scan.
        source_site: Source site name.
        records: List to append records to.
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return

    seen_paths = {r.fixture_path for r in records}

    for html_file in sorted(dir_path.glob("*.html")):
        fpath = str(html_file)
        if fpath in seen_paths:
            continue

        try:
            content = html_file.read_text(encoding="utf-8", errors="replace")
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            records.append(CrossSiteFixtureRecord(
                fixture_path=fpath,
                source_site=source_site,
                fixture_type="property_detail",
                content_hash=content_hash,
                content_length=len(content),
            ))
        except Exception as e:
            logger.debug(f"Could not read fixture {html_file}: {e}")


def process_cross_site_fixtures(
    root_dir: Optional[str] = None,
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    force_reprocess: bool = False,
) -> CrossSiteFixtureProcessingRunResult:
    """Process all cross-site fixtures from all supported sources.

    Args:
        root_dir: Root data directory override.
        database_path: Path to the SQLite database.
        output_dir: Output directory for manifest.
        force_reprocess: Reprocess even if content hash matches.

    Returns:
        CrossSiteFixtureProcessingRunResult with processing statistics.
    """
    run = CrossSiteFixtureProcessingRunResult()

    for source in SUPPORTED_SOURCES:
        source_result = process_cross_site_source_fixtures(
            source_site=source,
            root_dir=root_dir,
            database_path=database_path,
            output_dir=output_dir,
            force_reprocess=force_reprocess,
        )
        run.files_scanned += source_result.files_scanned
        run.files_processed += source_result.files_processed
        run.files_skipped += source_result.files_skipped
        run.files_failed += source_result.files_failed
        run.observations_inserted += source_result.observations_inserted
        run.candidates_matched += source_result.candidates_matched
        run.watched_properties_matched += source_result.watched_properties_matched
        run.duplicates_skipped += source_result.duplicates_skipped
        run.queue_items_marked_captured += source_result.queue_items_marked_captured
        run.warnings += source_result.warnings
        run.errors += source_result.errors
        run.results.extend(source_result.results)
        if source_result.files_scanned > 0:
            run.sources_processed.append(source)

    return run


def process_cross_site_source_fixtures(
    source_site: str,
    root_dir: Optional[str] = None,
    fixture_dir: Optional[str] = None,
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    force_reprocess: bool = False,
) -> CrossSiteFixtureProcessingRunResult:
    """Process cross-site fixtures for a single source.

    Args:
        source_site: Source site name (zillow, realtor, homes, compass).
        root_dir: Root data directory override.
        fixture_dir: Specific directory to process.
        database_path: Path to the SQLite database.
        output_dir: Output directory for manifest.
        force_reprocess: Reprocess even if content hash matches.

    Returns:
        CrossSiteFixtureProcessingRunResult with processing statistics.
    """
    run = CrossSiteFixtureProcessingRunResult()

    parser = _get_parser(source_site)
    if parser is None:
        logger.warning(f"No parser available for source: {source_site}")
        return run

    # Scan for fixtures
    records = scan_cross_site_fixtures(
        root_dir=root_dir,
        source_site=source_site,
        fixture_dir=fixture_dir,
    )
    run.files_scanned = len(records)

    if not records:
        return run

    # Load existing manifest to check for already-processed hashes
    processed_dir = Path(output_dir or "data/processed")
    manifest_path = processed_dir / MANIFEST_FILENAME
    processed_hashes = _load_processed_hashes(manifest_path)

    for record in records:
        if not force_reprocess and record.content_hash in processed_hashes:
            run.files_skipped += 1
            run.duplicates_skipped += 1
            record.already_processed = True
            continue

        # Process the fixture
        result = _process_single_fixture(
            record, parser, database_path,
        )
        run.results.append(result)

        if result.status == "processed":
            run.files_processed += 1
            run.observations_inserted += result.observations_inserted
            run.candidates_matched += result.candidates_matched
            run.watched_properties_matched += result.watched_properties_matched

            # Try to mark capture queue item as captured
            captured = _mark_capture_queue_item(
                record.fixture_path, source_site, database_path,
            )
            if captured:
                run.queue_items_marked_captured += 1
        elif result.status == "failed":
            run.files_failed += 1

        run.warnings += len(result.warnings)
        run.errors += len(result.errors)

    # Write manifest
    write_cross_site_processing_manifest(
        run.results, output_dir=output_dir,
    )

    return run


def write_cross_site_processing_manifest(
    results: List[CrossSiteFixtureProcessingResult],
    output_dir: Optional[str] = None,
) -> str:
    """Write or append to the cross-site processing manifest.

    Args:
        results: List of processing results to write.
        output_dir: Output directory for the manifest file.

    Returns:
        Path to the manifest file.
    """
    if not results:
        return ""

    processed_dir = Path(output_dir or "data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = processed_dir / MANIFEST_FILENAME

    file_exists = manifest_path.exists()

    with open(manifest_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDNAMES)
        if not file_exists:
            writer.writeheader()

        for result in results:
            if result.status not in ("processed", "failed"):
                continue
            writer.writerow({
                "processed_at": datetime.now().isoformat(),
                "source_site": result.source_site,
                "fixture_path": result.fixture_path,
                "source_url": result.source_url,
                "fixture_type": result.fixture_type,
                "status": result.status,
                "observations_inserted": str(result.observations_inserted),
                "candidates_matched": str(result.candidates_matched),
                "watched_properties_matched": str(
                    result.watched_properties_matched
                ),
                "warnings": "; ".join(result.warnings[:3]),
                "errors": "; ".join(result.errors[:3]),
                "content_hash": result.content_hash,
            })

    return str(manifest_path)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_cross_site_processing_summary(
    run: CrossSiteFixtureProcessingRunResult,
) -> str:
    """Format processing run result as a human-readable string.

    Args:
        run: Processing run result.

    Returns:
        Formatted string.
    """
    lines = [
        "=== Cross-Site Fixture Processing Summary ===",
        "",
        f"Sources processed: {', '.join(run.sources_processed) or '(none)'}",
        f"Files scanned:              {run.files_scanned}",
        f"Files processed:            {run.files_processed}",
        f"Files skipped (duplicate):  {run.files_skipped}",
        f"Files failed:               {run.files_failed}",
        "",
        f"Observations inserted:      {run.observations_inserted}",
        f"Candidates matched:         {run.candidates_matched}",
        f"Watched properties matched: {run.watched_properties_matched}",
        f"Duplicates skipped:         {run.duplicates_skipped}",
        f"Queue items marked captured: {run.queue_items_marked_captured}",
        f"Warnings:                   {run.warnings}",
        f"Errors:                     {run.errors}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_processed_hashes(manifest_path: Path) -> set:
    """Load content hashes from existing manifest.

    Args:
        manifest_path: Path to the manifest CSV.

    Returns:
        Set of content hashes already processed.
    """
    hashes: set = set()
    if not manifest_path.exists():
        return hashes

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                h = row.get("content_hash", "")
                status = row.get("status", "")
                if h and status == "processed":
                    hashes.add(h)
    except Exception as e:
        logger.debug(f"Could not load manifest hashes: {e}")

    return hashes


def _process_single_fixture(
    record: CrossSiteFixtureRecord,
    parser: Callable,
    database_path: Optional[str],
) -> CrossSiteFixtureProcessingResult:
    """Process a single cross-site fixture file.

    Args:
        record: Fixture record to process.
        parser: Parser function for this source.
        database_path: Path to the SQLite database.

    Returns:
        CrossSiteFixtureProcessingResult with processing status.
    """
    result = CrossSiteFixtureProcessingResult(
        fixture_path=record.fixture_path,
        source_site=record.source_site,
        fixture_type=record.fixture_type,
        content_hash=record.content_hash,
    )

    try:
        parse_result: CrossSiteParseResult = parser(Path(record.fixture_path))
    except Exception as e:
        result.status = "failed"
        result.errors.append(f"Parser error: {e}")
        return result

    if parse_result.parse_status == "failed" or not parse_result.property_facts:
        result.status = "failed"
        result.errors.extend(parse_result.errors)
        result.warnings.extend(parse_result.warnings)
        return result

    result.source_url = parse_result.source_url or ""
    result.warnings.extend(parse_result.warnings)

    # Try to insert observation via cross_site_enrichment
    try:
        from marketsentry.cross_site_enrichment import (
            _find_watched_property_for_observation,
            insert_cross_site_observation,
        )

        property_id = _find_watched_property_for_observation(
            parse_result, database_path,
        )

        if property_id:
            result.watched_properties_matched += 1
            inserted = insert_cross_site_observation(
                property_id, parse_result, database_path,
            )
            if inserted:
                result.observations_inserted += 1
    except Exception as e:
        result.warnings.append(f"Observation insert: {e}")

    result.status = "processed"
    return result


def _mark_capture_queue_item(
    fixture_path: str,
    source_site: str,
    database_path: Optional[str],
) -> bool:
    """Mark matching fixture capture queue items as captured.

    Args:
        fixture_path: Path to the processed fixture.
        source_site: Source site name.
        database_path: Path to the SQLite database.

    Returns:
        True if any item was marked captured.
    """
    try:
        from marketsentry.fixture_capture_queue import (
            list_pending_capture_requests,
            mark_fixture_captured,
        )

        pending = list_pending_capture_requests(
            source_site=source_site,
            database_path=database_path,
        )

        for item in pending:
            # Match by fixture path or source URL
            cap_id = item.get("capture_request_id")
            if cap_id:
                mark_fixture_captured(
                    capture_request_id=cap_id,
                    fixture_path=fixture_path,
                    database_path=database_path,
                )
                return True
    except Exception as e:
        logger.debug(f"Could not mark capture queue item: {e}")

    return False
