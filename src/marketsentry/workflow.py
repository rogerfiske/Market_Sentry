"""End-to-end workflow orchestration for Market_Sentry.

Provides orchestrated workflows that combine existing modules into
coherent operational sequences for candidate review, watchlist refresh,
and fixture-based demonstration.

No live network calls, scraping, or browser automation.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from marketsentry.config import config
from marketsentry.logging_config import logger
from marketsentry.models import (
    WorkflowError,
    WorkflowOutputFile,
    WorkflowRunResult,
    WorkflowStepResult,
    WorkflowWarning,
)


def _run_step(step_name: str) -> WorkflowStepResult:
    """Create and start a workflow step result."""
    step = WorkflowStepResult(
        step_name=step_name,
        status="running",
        started_at=datetime.now(),
    )
    return step


def _complete_step(step: WorkflowStepResult, status: str = "completed") -> None:
    """Mark a step as completed and calculate duration."""
    step.status = status
    step.completed_at = datetime.now()
    if step.started_at:
        step.duration_seconds = (
            step.completed_at - step.started_at
        ).total_seconds()


def _skip_step(step: WorkflowStepResult, reason: str) -> None:
    """Mark a step as skipped with a reason."""
    step.status = "skipped"
    step.notes = reason
    step.completed_at = datetime.now()
    if step.started_at:
        step.duration_seconds = (
            step.completed_at - step.started_at
        ).total_seconds()


def _fail_step(step: WorkflowStepResult, error_msg: str) -> None:
    """Mark a step as failed with an error message."""
    step.status = "failed"
    step.errors.append(error_msg)
    step.completed_at = datetime.now()
    if step.started_at:
        step.duration_seconds = (
            step.completed_at - step.started_at
        ).total_seconds()


def run_initial_review_workflow(
    database_path: Optional[str] = None,
    redfin_urls_file: Optional[str] = None,
    redfin_search_dir: Optional[str] = None,
    redfin_details_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> WorkflowRunResult:
    """Run the initial candidate review workflow.

    Prepares new candidates for user review by:
    1. Ensuring database is initialized/migrated.
    2. Importing Redfin URLs from CSV if file is present.
    3. Parsing Redfin search fixtures if directory exists.
    4. Parsing/enriching Redfin detail fixtures if directory exists.
    5. Recalculating candidate metrics.
    6. Persisting Effective DOM v2 where possible.
    7. Exporting candidate review CSV.
    8. Exporting candidate analysis report.

    No live network calls.

    Args:
        database_path: Path to SQLite database (default: from config).
        redfin_urls_file: Path to CSV with Redfin URLs.
        redfin_search_dir: Directory with saved Redfin search HTML fixtures.
        redfin_details_dir: Directory with saved Redfin detail HTML fixtures.
        output_dir: Directory for output reports.

    Returns:
        WorkflowRunResult with step results and output files.
    """
    from marketsentry.database import init_db, migrate_schema

    db_path = database_path or config.database_path
    out_dir = output_dir or config.data_exports_dir
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    result = WorkflowRunResult(
        workflow_name="initial_review",
        database_path=db_path,
        started_at=datetime.now(),
    )

    # Step 1: Initialize and migrate database
    step = _run_step("initialize_database")
    try:
        config.ensure_directories()
        init_db(db_path)
        migrate_schema(db_path)
        _complete_step(step)
        step.notes = "Database initialized and schema migrated"
    except Exception as e:
        _fail_step(step, f"Database initialization failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 2: Import Redfin URLs from CSV
    step = _run_step("import_redfin_urls")
    if redfin_urls_file and Path(redfin_urls_file).exists():
        try:
            from marketsentry.redfin_url_import import import_redfin_urls_from_csv

            url_result = import_redfin_urls_from_csv(redfin_urls_file, db_path)
            step.records_processed = url_result.total_rows_read
            step.records_created = url_result.candidates_inserted
            step.records_skipped = url_result.candidates_skipped
            _complete_step(step)
        except Exception as e:
            _fail_step(step, f"Redfin URL import failed: {e}")
            result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    else:
        _skip_step(step, "No Redfin URLs file provided or file not found")
    result.steps.append(step)

    # Step 3: Parse Redfin search fixtures
    step = _run_step("parse_redfin_search_fixtures")
    if redfin_search_dir and Path(redfin_search_dir).is_dir():
        try:
            from marketsentry.redfin_fixture_parser import parse_redfin_fixtures_from_directory

            search_result = parse_redfin_fixtures_from_directory(redfin_search_dir, db_path)
            step.records_processed = search_result.total_rows_read
            step.records_created = search_result.candidates_inserted
            step.records_skipped = search_result.candidates_skipped
            _complete_step(step)
        except Exception as e:
            _fail_step(step, f"Redfin search fixture parsing failed: {e}")
            result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    else:
        _skip_step(step, "No Redfin search directory provided or directory not found")
    result.steps.append(step)

    # Step 4: Parse/enrich Redfin detail fixtures
    step = _run_step("enrich_redfin_details")
    if redfin_details_dir and Path(redfin_details_dir).is_dir():
        try:
            from marketsentry.redfin_detail_enrichment import enrich_candidates_from_detail_directory

            enrich_result = enrich_candidates_from_detail_directory(redfin_details_dir, db_path)
            step.records_processed = enrich_result.total_files_processed
            step.records_updated = enrich_result.candidates_updated
            _complete_step(step)
        except Exception as e:
            _fail_step(step, f"Redfin detail enrichment failed: {e}")
            result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    else:
        _skip_step(step, "No Redfin details directory provided or directory not found")
    result.steps.append(step)

    # Step 5: Recalculate candidate metrics
    step = _run_step("recalculate_candidates")
    try:
        from marketsentry.candidate_recalc import recalculate_candidates

        recalc_result = recalculate_candidates(db_path)
        step.records_processed = recalc_result.candidates_scanned
        step.records_updated = recalc_result.candidates_updated
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Candidate recalculation failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 6: Persist Effective DOM v2
    step = _run_step("persist_effective_dom_v2")
    try:
        from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2

        v2_result = persist_effective_dom_v2(db_path)
        step.records_processed = v2_result.properties_scanned
        step.records_updated = v2_result.records_updated
        step.notes = (
            f"County resets applied: {v2_result.county_resets_applied}, "
            f"Churn preserved: {v2_result.churn_metrics_preserved}"
        )
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Effective DOM v2 persistence failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 7: Export candidate review CSV
    step = _run_step("export_candidate_review")
    try:
        from marketsentry.review_export import export_candidates_from_db

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        review_csv_path = str(Path(out_dir) / f"candidate_review_{timestamp}.csv")
        csv_path = export_candidates_from_db(review_csv_path, db_path)
        # Count rows
        row_count = _count_csv_rows(csv_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=csv_path,
            report_type="candidate_review",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=csv_path,
            report_type="candidate_review",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Candidate review export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 8: Export candidate analysis report
    step = _run_step("export_candidate_analysis")
    try:
        from marketsentry.candidate_report import export_candidate_analysis_report

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_path = str(Path(out_dir) / f"candidate_analysis_{timestamp}.csv")
        csv_path = export_candidate_analysis_report(db_path, analysis_path)
        row_count = _count_csv_rows(csv_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=csv_path,
            report_type="candidate_analysis",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=csv_path,
            report_type="candidate_analysis",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Candidate analysis export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Finalize result
    result.completed_at = datetime.now()
    if result.started_at:
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

    result.next_recommended_action = (
        "Review the candidate review CSV. "
        "Set user_decision to save/reject/maybe for each property. "
        "Then run: marketsentry import-review --file <reviewed_csv>"
    )

    # Generate summary and manifest
    summary_path = generate_workflow_summary(result, out_dir)
    result.summary_file = summary_path
    append_report_manifest(result, out_dir)

    return result


def run_watchlist_refresh_workflow(
    database_path: Optional[str] = None,
    redfin_details_dir: Optional[str] = None,
    cross_site_root_dir: Optional[str] = None,
    county_root_dir: Optional[str] = None,
    county_records_file: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> WorkflowRunResult:
    """Run the watchlist refresh workflow.

    Refreshes existing watched properties using available local data:
    1. Ensure database initialized/migrated.
    2. Parse/enrich Redfin detail fixtures if directory exists.
    3. Parse cross-site fixtures if directories exist.
    4. Parse/import county fixtures or CSV if present.
    5. Persist Effective DOM v2.
    6. Snapshot watchlist.
    7. Export watchlist monitoring report.
    8. Export Effective DOM v2 report.
    9. Export county verification report.

    No live network calls.

    Args:
        database_path: Path to SQLite database (default: from config).
        redfin_details_dir: Directory with saved Redfin detail HTML fixtures.
        cross_site_root_dir: Root directory with cross-site fixture subdirectories.
        county_root_dir: Root directory with county fixture subdirectories.
        county_records_file: Path to county records CSV.
        output_dir: Directory for output reports.

    Returns:
        WorkflowRunResult with step results and output files.
    """
    from marketsentry.database import init_db, migrate_schema

    db_path = database_path or config.database_path
    out_dir = output_dir or config.data_exports_dir
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    result = WorkflowRunResult(
        workflow_name="watchlist_refresh",
        database_path=db_path,
        started_at=datetime.now(),
    )

    # Step 1: Initialize and migrate database
    step = _run_step("initialize_database")
    try:
        config.ensure_directories()
        init_db(db_path)
        migrate_schema(db_path)
        _complete_step(step)
        step.notes = "Database initialized and schema migrated"
    except Exception as e:
        _fail_step(step, f"Database initialization failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 2: Parse/enrich Redfin detail fixtures
    step = _run_step("enrich_redfin_details")
    if redfin_details_dir and Path(redfin_details_dir).is_dir():
        try:
            from marketsentry.redfin_detail_enrichment import enrich_candidates_from_detail_directory

            enrich_result = enrich_candidates_from_detail_directory(redfin_details_dir, db_path)
            step.records_processed = enrich_result.total_files_processed
            step.records_updated = enrich_result.candidates_updated
            _complete_step(step)
        except Exception as e:
            _fail_step(step, f"Redfin detail enrichment failed: {e}")
            result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    else:
        _skip_step(step, "No Redfin details directory provided or directory not found")
    result.steps.append(step)

    # Step 3: Parse cross-site fixtures
    step = _run_step("parse_cross_site_fixtures")
    if cross_site_root_dir and Path(cross_site_root_dir).is_dir():
        try:
            from marketsentry.cross_site_enrichment import parse_cross_site_directory

            total_files = 0
            total_observations = 0
            total_matched = 0
            sources = ["zillow", "realtor", "homes", "compass"]
            for source in sources:
                source_dir = Path(cross_site_root_dir) / source
                if source_dir.is_dir():
                    cs_result = parse_cross_site_directory(str(source_dir), source, db_path)
                    total_files += cs_result.files_processed
                    total_observations += cs_result.observations_created
                    total_matched += cs_result.properties_matched

            step.records_processed = total_files
            step.records_created = total_observations
            step.notes = f"Properties matched: {total_matched}"
            _complete_step(step)
        except Exception as e:
            _fail_step(step, f"Cross-site fixture parsing failed: {e}")
            result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    else:
        _skip_step(step, "No cross-site root directory provided or directory not found")
    result.steps.append(step)

    # Step 4: Import county records
    step = _run_step("import_county_records")
    if county_records_file and Path(county_records_file).exists():
        try:
            from marketsentry.county_import import import_county_records_csv

            county_result = import_county_records_csv(county_records_file, db_path)
            step.records_processed = county_result.total_rows_read
            step.records_created = county_result.rows_inserted
            step.notes = f"Matched: {county_result.rows_matched}, Unmatched: {county_result.rows_unmatched}"
            _complete_step(step)
        except Exception as e:
            _fail_step(step, f"County records import failed: {e}")
            result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    elif county_root_dir and Path(county_root_dir).is_dir():
        try:
            from marketsentry.county_parser import parse_county_record_directory
            from marketsentry.county_import import _insert_county_record

            total_parsed = 0
            total_inserted = 0
            source_types = ["assessor", "recorder", "tax_collector", "permit"]
            for source_type in source_types:
                source_dir = Path(county_root_dir) / source_type
                if source_dir.is_dir():
                    results_list = parse_county_record_directory(source_dir, source_type)
                    for parse_result in results_list:
                        if parse_result.parse_status in ["success", "partial"]:
                            total_parsed += 1
                            if parse_result.county_record:
                                if _insert_county_record(parse_result.county_record, db_path):
                                    total_inserted += 1

            step.records_processed = total_parsed
            step.records_created = total_inserted
            _complete_step(step)
        except Exception as e:
            _fail_step(step, f"County fixture parsing failed: {e}")
            result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    else:
        _skip_step(step, "No county records file or directory provided")
    result.steps.append(step)

    # Step 5: Persist Effective DOM v2
    step = _run_step("persist_effective_dom_v2")
    try:
        from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2

        v2_result = persist_effective_dom_v2(db_path)
        step.records_processed = v2_result.properties_scanned
        step.records_updated = v2_result.records_updated
        step.notes = (
            f"County resets applied: {v2_result.county_resets_applied}, "
            f"Churn preserved: {v2_result.churn_metrics_preserved}"
        )
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Effective DOM v2 persistence failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 6: Snapshot watchlist
    step = _run_step("snapshot_watchlist")
    try:
        from marketsentry.monitoring import create_snapshots_for_all_watched

        snap_result = create_snapshots_for_all_watched(db_path)
        step.records_processed = snap_result.properties_scanned
        step.records_created = snap_result.snapshots_created
        step.notes = f"Changes detected: {snap_result.changes_detected_count}"
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Watchlist snapshot failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 7: Export watchlist monitoring report
    step = _run_step("export_watchlist_monitoring_report")
    try:
        from marketsentry.monitoring_report import export_watchlist_monitoring_report

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = str(Path(out_dir) / f"watchlist_monitoring_{timestamp}.csv")
        row_count = export_watchlist_monitoring_report(report_path, db_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=report_path,
            report_type="watchlist_monitoring",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=report_path,
            report_type="watchlist_monitoring",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Watchlist monitoring report export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 8: Export Effective DOM v2 report
    step = _run_step("export_effective_dom_v2_report")
    try:
        from marketsentry.effective_dom_v2_report import export_effective_dom_v2_report

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        v2_report_path = str(Path(out_dir) / f"effective_dom_v2_{timestamp}.csv")
        row_count = export_effective_dom_v2_report(v2_report_path, db_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=v2_report_path,
            report_type="effective_dom_v2",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=v2_report_path,
            report_type="effective_dom_v2",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Effective DOM v2 report export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 9: Export county verification report
    step = _run_step("export_county_verification_report")
    try:
        from marketsentry.county_verification_report import export_county_verification_report

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        county_report_path = str(Path(out_dir) / f"county_verification_{timestamp}.csv")
        row_count = export_county_verification_report(county_report_path, db_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=county_report_path,
            report_type="county_verification",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=county_report_path,
            report_type="county_verification",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"County verification report export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Finalize result
    result.completed_at = datetime.now()
    if result.started_at:
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

    result.next_recommended_action = (
        "Review the watchlist monitoring report for property changes. "
        "Check Effective DOM v2 and Churn Index values. "
        "County verification report shows ownership transfer evidence."
    )

    # Generate summary and manifest
    summary_path = generate_workflow_summary(result, out_dir)
    result.summary_file = summary_path
    append_report_manifest(result, out_dir)

    return result


def run_full_fixture_demo_workflow(
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    reset_demo_db: bool = False,
) -> WorkflowRunResult:
    """Run a deterministic fixture-based demonstration workflow.

    Uses sample/fixture data only. Does not depend on external websites.

    Steps:
    1. Use a configurable demo database path.
    2. Initialize database.
    3. Seed sample candidates.
    4. Recalculate candidate metrics.
    5. Persist Effective DOM v2.
    6. Export candidate review CSV.
    7. Simulate review decisions (mark first 2 as save, rest as reject).
    8. Import review decisions and promote saved candidates.
    9. Snapshot watchlist.
    10. Export all reports.
    11. Return a summary.

    No live network calls.

    Args:
        database_path: Path to demo database (default: db/demo_marketsentry.db).
        output_dir: Directory for output reports.
        reset_demo_db: Whether to delete existing demo database before starting.

    Returns:
        WorkflowRunResult with step results and output files.
    """
    from marketsentry.database import init_db, migrate_schema

    db_path = database_path or "db/demo_marketsentry.db"
    out_dir = output_dir or config.data_exports_dir
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    result = WorkflowRunResult(
        workflow_name="fixture_demo",
        database_path=db_path,
        started_at=datetime.now(),
    )

    # Optionally reset demo database
    if reset_demo_db and Path(db_path).exists():
        try:
            os.remove(db_path)
            result.warnings.append(WorkflowWarning(
                step_name="reset_demo_db",
                message=f"Deleted existing demo database: {db_path}",
            ))
        except OSError as e:
            result.errors.append(WorkflowError(
                step_name="reset_demo_db",
                message=f"Could not delete demo database: {e}",
            ))

    # Step 1: Initialize database
    step = _run_step("initialize_database")
    try:
        init_db(db_path)
        migrate_schema(db_path)
        _complete_step(step)
        step.notes = "Demo database initialized"
    except Exception as e:
        _fail_step(step, f"Database initialization failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 2: Seed sample candidates
    step = _run_step("seed_sample_candidates")
    try:
        from marketsentry.sample_data import seed_sample_candidates

        count = seed_sample_candidates(db_path)
        step.records_created = count
        _complete_step(step)
        step.notes = f"Seeded {count} sample candidates"
    except Exception as e:
        _fail_step(step, f"Sample candidate seeding failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 3: Recalculate candidate metrics
    step = _run_step("recalculate_candidates")
    try:
        from marketsentry.candidate_recalc import recalculate_candidates

        recalc_result = recalculate_candidates(db_path)
        step.records_processed = recalc_result.candidates_scanned
        step.records_updated = recalc_result.candidates_updated
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Candidate recalculation failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 4: Persist Effective DOM v2
    step = _run_step("persist_effective_dom_v2")
    try:
        from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2

        v2_result = persist_effective_dom_v2(db_path)
        step.records_processed = v2_result.properties_scanned
        step.records_updated = v2_result.records_updated
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Effective DOM v2 persistence failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 5: Export candidate review CSV
    step = _run_step("export_candidate_review")
    review_csv_path = None
    try:
        from marketsentry.review_export import export_candidates_from_db

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        review_csv_path = str(Path(out_dir) / f"demo_candidate_review_{timestamp}.csv")
        csv_path = export_candidates_from_db(review_csv_path, db_path)
        review_csv_path = csv_path
        row_count = _count_csv_rows(csv_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=csv_path,
            report_type="candidate_review",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=csv_path,
            report_type="candidate_review",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Candidate review export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 6: Simulate review decisions
    step = _run_step("simulate_review_decisions")
    reviewed_csv_path = None
    if review_csv_path and Path(review_csv_path).exists():
        try:
            reviewed_csv_path = _simulate_review_decisions(review_csv_path, out_dir)
            row_count = _count_csv_rows(reviewed_csv_path)
            step.records_processed = row_count
            _complete_step(step)
            step.notes = "Simulated review: first 2 candidates saved, rest rejected"
        except Exception as e:
            _fail_step(step, f"Review decision simulation failed: {e}")
            result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    else:
        _skip_step(step, "No review CSV available to simulate decisions")
    result.steps.append(step)

    # Step 7: Import review decisions and promote
    step = _run_step("import_review_decisions")
    if reviewed_csv_path and Path(reviewed_csv_path).exists():
        try:
            from marketsentry.review_import import process_review_decisions

            counts = process_review_decisions(reviewed_csv_path, db_path)
            step.records_processed = counts.get("total", 0)
            step.records_updated = counts.get("processed", 0)
            step.notes = (
                f"Save: {counts.get('save', 0)}, "
                f"Reject: {counts.get('reject', 0)}, "
                f"Promoted: {counts.get('promoted', 0)}"
            )
            _complete_step(step)
        except Exception as e:
            _fail_step(step, f"Review decision import failed: {e}")
            result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    else:
        _skip_step(step, "No reviewed CSV available")
    result.steps.append(step)

    # Step 8: Snapshot watchlist
    step = _run_step("snapshot_watchlist")
    try:
        from marketsentry.monitoring import create_snapshots_for_all_watched

        snap_result = create_snapshots_for_all_watched(db_path)
        step.records_processed = snap_result.properties_scanned
        step.records_created = snap_result.snapshots_created
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Watchlist snapshot failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Step 9: Export all reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Candidate analysis report
    step = _run_step("export_candidate_analysis")
    try:
        from marketsentry.candidate_report import export_candidate_analysis_report

        analysis_path = str(Path(out_dir) / f"demo_candidate_analysis_{timestamp}.csv")
        csv_path = export_candidate_analysis_report(db_path, analysis_path)
        row_count = _count_csv_rows(csv_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=csv_path,
            report_type="candidate_analysis",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=csv_path,
            report_type="candidate_analysis",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Candidate analysis export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Watchlist monitoring report
    step = _run_step("export_watchlist_monitoring_report")
    try:
        from marketsentry.monitoring_report import export_watchlist_monitoring_report

        monitor_path = str(Path(out_dir) / f"demo_watchlist_monitoring_{timestamp}.csv")
        row_count = export_watchlist_monitoring_report(monitor_path, db_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=monitor_path,
            report_type="watchlist_monitoring",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=monitor_path,
            report_type="watchlist_monitoring",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Watchlist monitoring report export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Effective DOM v2 report
    step = _run_step("export_effective_dom_v2_report")
    try:
        from marketsentry.effective_dom_v2_report import export_effective_dom_v2_report

        v2_report_path = str(Path(out_dir) / f"demo_effective_dom_v2_{timestamp}.csv")
        row_count = export_effective_dom_v2_report(v2_report_path, db_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=v2_report_path,
            report_type="effective_dom_v2",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=v2_report_path,
            report_type="effective_dom_v2",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"Effective DOM v2 report export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # County verification report
    step = _run_step("export_county_verification_report")
    try:
        from marketsentry.county_verification_report import export_county_verification_report

        county_report_path = str(Path(out_dir) / f"demo_county_verification_{timestamp}.csv")
        row_count = export_county_verification_report(county_report_path, db_path)
        step.records_processed = row_count
        step.output_files.append(WorkflowOutputFile(
            file_path=county_report_path,
            report_type="county_verification",
            row_count=row_count,
        ))
        result.output_files.append(WorkflowOutputFile(
            file_path=county_report_path,
            report_type="county_verification",
            row_count=row_count,
        ))
        _complete_step(step)
    except Exception as e:
        _fail_step(step, f"County verification report export failed: {e}")
        result.errors.append(WorkflowError(step_name=step.step_name, message=str(e)))
    result.steps.append(step)

    # Finalize result
    result.completed_at = datetime.now()
    if result.started_at:
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

    result.next_recommended_action = (
        "Demo workflow complete. Review generated reports in the output directory. "
        "To start with real data, save Redfin search/detail pages as HTML fixtures "
        "and run: marketsentry run-initial-review-workflow"
    )

    # Generate summary and manifest
    summary_path = generate_workflow_summary(result, out_dir)
    result.summary_file = summary_path
    append_report_manifest(result, out_dir)

    return result


def generate_workflow_summary(
    result: WorkflowRunResult,
    output_dir: Optional[str] = None,
) -> str:
    """Generate a markdown summary file for a workflow run.

    Args:
        result: The workflow run result to summarize.
        output_dir: Directory for the summary file.

    Returns:
        Path to the generated summary file.
    """
    out_dir = output_dir or config.data_exports_dir
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = str(Path(out_dir) / f"workflow_summary_{timestamp}.md")

    lines: List[str] = []
    lines.append(f"# Workflow Summary: {result.workflow_name}")
    lines.append("")
    lines.append(f"- **Start time:** {result.started_at.isoformat() if result.started_at else 'N/A'}")
    lines.append(f"- **End time:** {result.completed_at.isoformat() if result.completed_at else 'N/A'}")
    lines.append(f"- **Duration:** {result.duration_seconds:.1f}s" if result.duration_seconds else "- **Duration:** N/A")
    lines.append(f"- **Database:** {result.database_path}")
    lines.append("")

    # Steps summary
    lines.append("## Steps")
    lines.append("")
    lines.append("| Step | Status | Records Processed | Created | Updated | Skipped | Duration |")
    lines.append("|------|--------|-------------------|---------|---------|---------|----------|")

    total_processed = 0
    total_created = 0
    total_updated = 0
    total_skipped = 0

    for step_result in result.steps:
        duration_str = f"{step_result.duration_seconds:.1f}s" if step_result.duration_seconds else "N/A"
        lines.append(
            f"| {step_result.step_name} | {step_result.status} | "
            f"{step_result.records_processed} | {step_result.records_created} | "
            f"{step_result.records_updated} | {step_result.records_skipped} | "
            f"{duration_str} |"
        )
        total_processed += step_result.records_processed
        total_created += step_result.records_created
        total_updated += step_result.records_updated
        total_skipped += step_result.records_skipped

    lines.append(
        f"| **TOTAL** | | {total_processed} | {total_created} | "
        f"{total_updated} | {total_skipped} | |"
    )
    lines.append("")

    # Warnings
    all_warnings = list(result.warnings)
    for step_result in result.steps:
        for w in step_result.warnings:
            all_warnings.append(WorkflowWarning(step_name=step_result.step_name, message=w))

    if all_warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in all_warnings:
            lines.append(f"- [{w.step_name}] {w.message}")
        lines.append("")

    # Errors
    all_errors = list(result.errors)
    for step_result in result.steps:
        for e in step_result.errors:
            all_errors.append(WorkflowError(step_name=step_result.step_name, message=e))

    if all_errors:
        lines.append("## Errors")
        lines.append("")
        for e in all_errors:
            lines.append(f"- [{e.step_name}] {e.message}")
        lines.append("")

    # Output files
    if result.output_files:
        lines.append("## Output Files")
        lines.append("")
        lines.append("| Report Type | File Path | Row Count |")
        lines.append("|-------------|-----------|-----------|")
        for out_file in result.output_files:
            row_str = str(out_file.row_count) if out_file.row_count is not None else "N/A"
            lines.append(f"| {out_file.report_type} | {out_file.file_path} | {row_str} |")
        lines.append("")

    # Step notes
    step_notes = [s for s in result.steps if s.notes]
    if step_notes:
        lines.append("## Step Notes")
        lines.append("")
        for s in step_notes:
            lines.append(f"- **{s.step_name}:** {s.notes}")
        lines.append("")

    # Next recommended action
    if result.next_recommended_action:
        lines.append("## Next Recommended Action")
        lines.append("")
        lines.append(result.next_recommended_action)
        lines.append("")

    # Disclaimer
    lines.append("---")
    lines.append("")
    lines.append("*This is an analytical workflow summary, not a purchase recommendation.*")
    lines.append("*No live network calls or scraping were performed.*")
    lines.append("")

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Workflow summary written to {summary_path}")
    return summary_path


def append_report_manifest(
    result: WorkflowRunResult,
    output_dir: Optional[str] = None,
) -> str:
    """Append workflow output files to the report manifest CSV.

    Creates the manifest file if it does not exist.

    Args:
        result: The workflow run result containing output files.
        output_dir: Directory for the manifest file.

    Returns:
        Path to the manifest file.
    """
    out_dir = output_dir or config.data_exports_dir
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    manifest_path = str(Path(out_dir) / "report_manifest.csv")
    file_exists = Path(manifest_path).exists()

    fieldnames = [
        "created_at",
        "workflow_name",
        "report_type",
        "file_path",
        "row_count",
        "notes",
    ]

    with open(manifest_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        now_str = datetime.now().isoformat()

        # Add output file entries
        for out_file in result.output_files:
            writer.writerow({
                "created_at": now_str,
                "workflow_name": result.workflow_name,
                "report_type": out_file.report_type,
                "file_path": out_file.file_path,
                "row_count": out_file.row_count if out_file.row_count is not None else "",
                "notes": out_file.notes,
            })

        # Add summary file entry
        if result.summary_file:
            writer.writerow({
                "created_at": now_str,
                "workflow_name": result.workflow_name,
                "report_type": "workflow_summary",
                "file_path": result.summary_file,
                "row_count": "",
                "notes": f"Workflow: {result.workflow_name}",
            })

    logger.info(f"Report manifest updated at {manifest_path}")
    return manifest_path


def get_workflow_status(database_path: Optional[str] = None) -> dict:
    """Get current workflow status with table counts.

    Args:
        database_path: Path to database (default: from config).

    Returns:
        Dictionary with table counts and latest report info.
    """
    from marketsentry.database import get_table_count, table_exists

    db_path = database_path or config.database_path

    status: dict = {
        "database_path": db_path,
        "database_exists": Path(db_path).exists(),
        "tables": {},
        "latest_reports": [],
    }

    if not status["database_exists"]:
        return status

    table_names = [
        "candidate_review_queue",
        "watched_properties",
        "listing_events",
        "cross_site_observations",
        "county_record_observations",
        "property_observation_snapshots",
    ]

    for table_name in table_names:
        if table_exists(table_name, db_path):
            status["tables"][table_name] = get_table_count(table_name, db_path)
        else:
            status["tables"][table_name] = 0

    # Check for latest reports in exports directory
    exports_dir = Path(config.data_exports_dir)
    if exports_dir.exists():
        report_patterns = [
            "candidate_review_*.csv",
            "candidate_analysis_*.csv",
            "watchlist_monitoring_*.csv",
            "effective_dom_v2_*.csv",
            "county_verification_*.csv",
            "workflow_summary_*.md",
        ]
        for pattern in report_patterns:
            files = sorted(exports_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            if files:
                latest = files[0]
                status["latest_reports"].append({
                    "file": str(latest),
                    "modified": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(),
                })

    return status


def _count_csv_rows(file_path: str) -> int:
    """Count data rows in a CSV file (excluding header).

    Args:
        file_path: Path to CSV file.

    Returns:
        Number of data rows.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return sum(1 for _ in reader)
    except Exception:
        return 0


def _simulate_review_decisions(
    review_csv_path: str,
    output_dir: str,
) -> str:
    """Simulate review decisions for demo workflow.

    Marks first 2 candidates as 'save' and rest as 'reject'.

    Args:
        review_csv_path: Path to the exported review CSV.
        output_dir: Directory for the reviewed CSV output.

    Returns:
        Path to the reviewed CSV file.
    """
    rows = []
    with open(review_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for i, row in enumerate(reader):
            if i < 2:
                row["user_decision"] = "save"
                row["user_notes"] = "Demo: auto-saved for demonstration"
            else:
                row["user_decision"] = "reject"
                row["user_notes"] = "Demo: auto-rejected for demonstration"
            rows.append(row)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reviewed_path = str(Path(output_dir) / f"demo_reviewed_{timestamp}.csv")

    with open(reviewed_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return reviewed_path
