"""Guided operator workflow for candidate management.

Provides workflow status, one-command refresh, candidate action
helpers (decision, location scores, noise notes), and action
summary export. Reduces command-line and CSV-editing burden.

This module does NOT perform live retrieval, send outbound
notifications, add walkability fields, or modify the Quiet
Score gatekeeper. Candidate mutations occur only through
explicit operator actions.
"""

import csv
import io
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------


class OperatorWorkflowStep(BaseModel):
    """A step in the operator workflow."""

    step_id: str = ""
    description: str = ""
    status: str = "not_run"
    detail: str = ""


class OperatorWorkflowWarning(BaseModel):
    """A warning from the operator workflow."""

    warning_id: str = ""
    message: str = ""
    severity: str = "info"


class OperatorWorkflowAction(BaseModel):
    """A recommended operator action."""

    action_id: str = ""
    description: str = ""
    priority: str = "normal"
    command: str = ""


class OperatorCandidateActionResult(BaseModel):
    """Result of a candidate action."""

    candidate_id: int = 0
    action: str = ""
    success: bool = False
    detail: str = ""
    promoted_property_id: Optional[int] = None


class OperatorWorkflowStatus(BaseModel):
    """Operator workflow status summary."""

    total_candidates: int = 0
    pending_candidates: int = 0
    maybe_candidates: int = 0
    saved_candidates: int = 0
    rejected_candidates: int = 0
    hold_candidates: int = 0
    active_watched: int = 0
    missing_quiet_vibrancy: int = 0
    missing_price: int = 0
    missing_enrichment: int = 0
    needing_review: int = 0
    latest_reports: List[str] = Field(
        default_factory=list
    )
    recommended_actions: List[OperatorWorkflowAction] = (
        Field(default_factory=list)
    )


class OperatorWorkflowRunResult(BaseModel):
    """Result of operator workflow run."""

    steps: List[OperatorWorkflowStep] = Field(
        default_factory=list
    )
    warnings: List[OperatorWorkflowWarning] = Field(
        default_factory=list
    )
    output_paths: List[str] = Field(
        default_factory=list
    )
    status: OperatorWorkflowStatus = Field(
        default_factory=OperatorWorkflowStatus
    )


# -------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------


VALID_DECISIONS = {
    "save", "reject", "maybe", "hold_for_more_data",
}

VALID_NOISE_RISKS = {
    "low", "moderate", "high", "severe", "unknown",
}


def build_operator_workflow_status(
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
) -> OperatorWorkflowStatus:
    """Build operator workflow status summary.

    Reads database to count candidates by status, missing
    data, and watched properties. Scans exports directory
    for latest reports. Does not mutate any state.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Path to exports directory.

    Returns:
        Operator workflow status summary.
    """
    if db_path is None:
        db_path = "data/market_sentry.db"
    if exports_dir is None:
        exports_dir = "data/exports"

    status = OperatorWorkflowStatus()

    # Read candidate counts from database
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Total candidates
        cur.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        )
        status.total_candidates = cur.fetchone()[0]

        # By decision
        for decision, attr in [
            ("pending", "pending_candidates"),
            ("maybe", "maybe_candidates"),
            ("save", "saved_candidates"),
            ("reject", "rejected_candidates"),
            ("hold_for_more_data", "hold_candidates"),
        ]:
            if decision == "pending":
                cur.execute(
                    "SELECT COUNT(*) FROM "
                    "candidate_review_queue "
                    "WHERE review_status = 'pending' "
                    "OR user_decision IS NULL"
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) FROM "
                    "candidate_review_queue "
                    "WHERE user_decision = ?",
                    (decision,),
                )
            setattr(status, attr, cur.fetchone()[0])

        # Missing quiet/vibrancy
        cur.execute(
            "SELECT COUNT(*) FROM "
            "candidate_review_queue "
            "WHERE quiet_score IS NULL "
            "OR vibrancy_score IS NULL"
        )
        status.missing_quiet_vibrancy = cur.fetchone()[0]

        # Missing price
        cur.execute(
            "SELECT COUNT(*) FROM "
            "candidate_review_queue "
            "WHERE price IS NULL"
        )
        status.missing_price = cur.fetchone()[0]

        # Missing enrichment (no beds/baths/sqft)
        cur.execute(
            "SELECT COUNT(*) FROM "
            "candidate_review_queue "
            "WHERE beds IS NULL "
            "AND baths IS NULL "
            "AND sqft IS NULL"
        )
        status.missing_enrichment = cur.fetchone()[0]

        # Needing review (pending after enrichment)
        cur.execute(
            "SELECT COUNT(*) FROM "
            "candidate_review_queue "
            "WHERE review_status = 'pending' "
            "AND (beds IS NOT NULL "
            "OR baths IS NOT NULL "
            "OR sqft IS NOT NULL)"
        )
        status.needing_review = cur.fetchone()[0]

        # Active watched properties
        cur.execute(
            "SELECT COUNT(*) FROM watched_properties "
            "WHERE active_watch_status = 1"
        )
        status.active_watched = cur.fetchone()[0]

        conn.close()
    except Exception:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    # Scan latest reports
    exp = Path(exports_dir)
    if exp.exists():
        report_patterns = [
            "candidate_analysis_*.md",
            "monitoring_report_*.md",
            "operations_digest_*.md",
            "portfolio_review_pack_*.md",
            "operator_action_summary_*.md",
        ]
        for pat in report_patterns:
            files = sorted(
                exp.glob(pat),
                key=lambda p: p.stat().st_mtime
                if p.exists()
                else 0,
                reverse=True,
            )
            if files:
                status.latest_reports.append(
                    str(files[0])
                )

    # Build recommended actions
    actions: List[OperatorWorkflowAction] = []

    if status.missing_quiet_vibrancy > 0:
        actions.append(
            OperatorWorkflowAction(
                action_id="enter_scores",
                description=(
                    f"{status.missing_quiet_vibrancy} "
                    f"candidates missing Quiet/Vibrancy "
                    f"scores"
                ),
                priority="high",
                command=(
                    "marketsentry candidate-location-scores"
                    " --candidate-id <id>"
                    " --quiet-score <value>"
                    " --vibrancy-score <value>"
                ),
            )
        )

    if status.missing_price > 0:
        actions.append(
            OperatorWorkflowAction(
                action_id="enter_price",
                description=(
                    f"{status.missing_price} candidates "
                    f"missing price"
                ),
                priority="high",
                command=(
                    "Review and enrich candidate data"
                ),
            )
        )

    if status.needing_review > 0:
        actions.append(
            OperatorWorkflowAction(
                action_id="review_candidates",
                description=(
                    f"{status.needing_review} candidates "
                    f"need review decisions"
                ),
                priority="high",
                command=(
                    "marketsentry candidate-decision"
                    " --candidate-id <id>"
                    " --decision <save|reject|maybe>"
                ),
            )
        )

    if status.pending_candidates > 0:
        actions.append(
            OperatorWorkflowAction(
                action_id="review_pending",
                description=(
                    f"{status.pending_candidates} "
                    f"pending candidates"
                ),
                priority="normal",
                command=(
                    "marketsentry operator-workflow-status"
                ),
            )
        )

    if status.total_candidates > 0:
        actions.append(
            OperatorWorkflowAction(
                action_id="refresh_reports",
                description=(
                    "Run operator refresh to update "
                    "all local reports"
                ),
                priority="normal",
                command=(
                    "marketsentry "
                    "run-operator-refresh-workflow"
                ),
            )
        )

    status.recommended_actions = actions
    return status


def run_operator_refresh_workflow(
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
) -> OperatorWorkflowRunResult:
    """Run the operator refresh workflow.

    Runs local-only operations in order:
    1. Recalc candidates
    2. Snapshot watchlist
    3. Export monitoring report
    4. Export candidate analysis
    5. Export operations digest
    6. Export portfolio review pack
    7. Export local operations bundle

    Does not run live retrieval, import decisions, mutate
    decisions, mutate alerts, or send notifications.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Path to exports directory.

    Returns:
        Workflow run result with steps and outputs.
    """
    if db_path is None:
        db_path = "data/market_sentry.db"
    if exports_dir is None:
        exports_dir = "data/exports"

    result = OperatorWorkflowRunResult()
    steps: List[OperatorWorkflowStep] = []
    warnings: List[OperatorWorkflowWarning] = []
    output_paths: List[str] = []

    db_file = Path(db_path)
    if not db_file.is_file():
        warnings.append(
            OperatorWorkflowWarning(
                warning_id="no_database",
                message=(
                    f"Database not found: {db_path}"
                ),
                severity="warning",
            )
        )
        result.warnings = warnings
        result.steps = [
            OperatorWorkflowStep(
                step_id="check_db",
                description="Check database exists",
                status="fail",
                detail=f"Database not found: {db_path}",
            )
        ]
        return result

    # Step 1: Recalc candidates
    try:
        from marketsentry.candidate_recalc import (
            recalc_all_candidates,
        )

        recalc_all_candidates(database_path=db_path)
        steps.append(
            OperatorWorkflowStep(
                step_id="recalc",
                description="Recalculate candidates",
                status="pass",
                detail="Candidates recalculated",
            )
        )
    except Exception as e:
        steps.append(
            OperatorWorkflowStep(
                step_id="recalc",
                description="Recalculate candidates",
                status="warning",
                detail=f"Recalc skipped: {e}",
            )
        )
        warnings.append(
            OperatorWorkflowWarning(
                warning_id="recalc_skip",
                message=f"Candidate recalc skipped: {e}",
                severity="warning",
            )
        )

    # Step 2: Snapshot watchlist
    try:
        from marketsentry.monitoring import (
            snapshot_watchlist_observations,
        )

        snapshot_watchlist_observations(
            database_path=db_path
        )
        steps.append(
            OperatorWorkflowStep(
                step_id="snapshot",
                description="Snapshot watchlist",
                status="pass",
                detail="Watchlist snapshots created",
            )
        )
    except Exception as e:
        steps.append(
            OperatorWorkflowStep(
                step_id="snapshot",
                description="Snapshot watchlist",
                status="warning",
                detail=f"Snapshot skipped: {e}",
            )
        )
        warnings.append(
            OperatorWorkflowWarning(
                warning_id="snapshot_skip",
                message=(
                    f"Watchlist snapshot skipped: {e}"
                ),
                severity="warning",
            )
        )

    # Step 3: Export monitoring report
    try:
        from marketsentry.monitoring import (
            export_monitoring_report,
        )

        paths = export_monitoring_report(
            database_path=db_path,
            output_dir=exports_dir,
        )
        if paths:
            output_paths.extend(
                paths if isinstance(paths, list)
                else [str(paths)]
            )
        steps.append(
            OperatorWorkflowStep(
                step_id="monitoring_report",
                description="Export monitoring report",
                status="pass",
                detail="Monitoring report exported",
            )
        )
    except Exception as e:
        steps.append(
            OperatorWorkflowStep(
                step_id="monitoring_report",
                description="Export monitoring report",
                status="warning",
                detail=f"Monitoring report skipped: {e}",
            )
        )
        warnings.append(
            OperatorWorkflowWarning(
                warning_id="monitoring_skip",
                message=(
                    f"Monitoring report skipped: {e}"
                ),
                severity="warning",
            )
        )

    # Step 4: Export candidate analysis
    try:
        from marketsentry.candidate_report import (
            export_candidate_analysis_report,
        )

        report_path = export_candidate_analysis_report(
            database_path=db_path,
            output_dir=exports_dir,
        )
        if report_path:
            output_paths.append(str(report_path))
        steps.append(
            OperatorWorkflowStep(
                step_id="candidate_report",
                description="Export candidate analysis",
                status="pass",
                detail="Candidate analysis exported",
            )
        )
    except Exception as e:
        steps.append(
            OperatorWorkflowStep(
                step_id="candidate_report",
                description="Export candidate analysis",
                status="warning",
                detail=(
                    f"Candidate analysis skipped: {e}"
                ),
            )
        )
        warnings.append(
            OperatorWorkflowWarning(
                warning_id="candidate_report_skip",
                message=(
                    f"Candidate analysis skipped: {e}"
                ),
                severity="warning",
            )
        )

    # Step 5: Export operations digest
    try:
        from marketsentry.operations_digest import (
            export_operations_digest,
        )

        digest_paths = export_operations_digest(
            database_path=db_path,
            output_dir=exports_dir,
        )
        if digest_paths:
            output_paths.extend(
                digest_paths
                if isinstance(digest_paths, list)
                else [str(digest_paths)]
            )
        steps.append(
            OperatorWorkflowStep(
                step_id="ops_digest",
                description="Export operations digest",
                status="pass",
                detail="Operations digest exported",
            )
        )
    except Exception as e:
        steps.append(
            OperatorWorkflowStep(
                step_id="ops_digest",
                description="Export operations digest",
                status="warning",
                detail=(
                    f"Operations digest skipped: {e}"
                ),
            )
        )
        warnings.append(
            OperatorWorkflowWarning(
                warning_id="ops_digest_skip",
                message=(
                    f"Operations digest skipped: {e}"
                ),
                severity="warning",
            )
        )

    # Step 6: Export portfolio review pack
    try:
        from marketsentry.portfolio_review_pack import (
            export_portfolio_review_pack,
        )

        pack_paths = export_portfolio_review_pack(
            database_path=db_path,
            output_dir=exports_dir,
        )
        if pack_paths:
            output_paths.extend(
                pack_paths
                if isinstance(pack_paths, list)
                else [str(pack_paths)]
            )
        steps.append(
            OperatorWorkflowStep(
                step_id="review_pack",
                description=(
                    "Export portfolio review pack"
                ),
                status="pass",
                detail="Portfolio review pack exported",
            )
        )
    except Exception as e:
        steps.append(
            OperatorWorkflowStep(
                step_id="review_pack",
                description=(
                    "Export portfolio review pack"
                ),
                status="warning",
                detail=(
                    f"Portfolio review pack skipped: {e}"
                ),
            )
        )
        warnings.append(
            OperatorWorkflowWarning(
                warning_id="review_pack_skip",
                message=(
                    f"Portfolio review pack skipped: {e}"
                ),
                severity="warning",
            )
        )

    # Step 7: Export local operations bundle
    try:
        from marketsentry.local_operations_bundle import (
            build_local_operations_bundle,
            export_local_operations_bundle,
        )

        bundle = build_local_operations_bundle(
            db_path=db_path,
            exports_dir=exports_dir,
        )
        exported = export_local_operations_bundle(
            bundle,
            output_dir=exports_dir,
            fmt="both",
        )
        if exported.output_paths:
            output_paths.extend(exported.output_paths)
        steps.append(
            OperatorWorkflowStep(
                step_id="ops_bundle",
                description=(
                    "Export local operations bundle"
                ),
                status="pass",
                detail="Operations bundle exported",
            )
        )
    except Exception as e:
        steps.append(
            OperatorWorkflowStep(
                step_id="ops_bundle",
                description=(
                    "Export local operations bundle"
                ),
                status="warning",
                detail=(
                    f"Operations bundle skipped: {e}"
                ),
            )
        )
        warnings.append(
            OperatorWorkflowWarning(
                warning_id="ops_bundle_skip",
                message=(
                    f"Operations bundle skipped: {e}"
                ),
                severity="warning",
            )
        )

    # Build final status
    status = build_operator_workflow_status(
        db_path=db_path, exports_dir=exports_dir
    )

    result.steps = steps
    result.warnings = warnings
    result.output_paths = output_paths
    result.status = status
    return result


def apply_candidate_decision(
    candidate_id: int,
    decision: str,
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
) -> OperatorCandidateActionResult:
    """Apply a candidate review decision.

    Save promotes to watchlist. Reject/maybe/hold update
    the review decision. Records user_review_actions.
    Does not duplicate watchlist promotion.

    Args:
        candidate_id: Candidate ID.
        decision: One of save, reject, maybe,
            hold_for_more_data.
        notes: Optional notes.
        db_path: Path to SQLite database.

    Returns:
        Action result with success status and detail.
    """
    if db_path is None:
        db_path = "data/market_sentry.db"

    result = OperatorCandidateActionResult(
        candidate_id=candidate_id,
        action=f"decision:{decision}",
    )

    # Validate decision
    if decision not in VALID_DECISIONS:
        result.detail = (
            f"Invalid decision: {decision}. "
            f"Valid: {', '.join(sorted(VALID_DECISIONS))}"
        )
        return result

    # Validate candidate exists
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM candidate_review_queue "
            "WHERE candidate_id = ?",
            (candidate_id,),
        )
        row = cur.fetchone()
        conn.close()

        if row is None:
            result.detail = (
                f"Candidate {candidate_id} not found"
            )
            return result
    except Exception as e:
        result.detail = f"Database error: {e}"
        return result

    # Append notes to existing if present
    existing_notes = row["user_notes"] or ""
    if notes:
        if existing_notes:
            combined_notes = (
                f"{existing_notes}\n{notes}"
            )
        else:
            combined_notes = notes
    else:
        combined_notes = existing_notes or None

    try:
        from marketsentry.database import (
            record_review_action,
            update_candidate_decision,
        )

        # Update decision
        update_candidate_decision(
            candidate_id=candidate_id,
            user_decision=decision,
            user_notes=combined_notes,
            database_path=db_path,
        )

        promoted_id = None

        if decision == "save":
            from marketsentry.watchlist import (
                promote_candidate_to_watchlist,
            )

            promoted_id = (
                promote_candidate_to_watchlist(
                    candidate_id=candidate_id,
                    database_path=db_path,
                )
            )
            if promoted_id is not None:
                result.promoted_property_id = promoted_id
                result.detail = (
                    f"Saved and promoted to watched "
                    f"property {promoted_id}"
                )
            else:
                result.detail = (
                    "Saved (already on watchlist "
                    "or promotion skipped)"
                )
        else:
            result.detail = (
                f"Decision updated to '{decision}'"
            )

        # Record review action
        record_review_action(
            candidate_id=candidate_id,
            user_decision=decision,
            user_notes=notes,
            promoted_property_id=promoted_id,
            database_path=db_path,
        )

        result.success = True

    except Exception as e:
        result.detail = f"Action failed: {e}"

    return result


def apply_candidate_location_scores(
    candidate_id: int,
    quiet_score: float,
    vibrancy_score: float,
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
) -> OperatorCandidateActionResult:
    """Update candidate Quiet and Vibrancy scores.

    Computes quiet_gatekeeper_result using existing
    gatekeeper rules. Quiet >= 7.0 passes; < 7.0 fails
    with noise risk. Low vibrancy does not override poor
    Quiet.

    Args:
        candidate_id: Candidate ID.
        quiet_score: Quiet score (0-10 scale).
        vibrancy_score: Vibrancy score (0-10 scale).
        notes: Optional notes.
        db_path: Path to SQLite database.

    Returns:
        Action result with success status and detail.
    """
    if db_path is None:
        db_path = "data/market_sentry.db"

    result = OperatorCandidateActionResult(
        candidate_id=candidate_id,
        action="location_scores",
    )

    # Validate candidate exists
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM candidate_review_queue "
            "WHERE candidate_id = ?",
            (candidate_id,),
        )
        row = cur.fetchone()

        if row is None:
            conn.close()
            result.detail = (
                f"Candidate {candidate_id} not found"
            )
            return result

        # Apply gatekeeper
        from marketsentry.quiet_vibrancy import (
            apply_quiet_gatekeeper,
        )

        gatekeeper_result, gatekeeper_detail = (
            apply_quiet_gatekeeper(
                quiet_score, vibrancy_score
            )
        )

        # Append notes
        existing_notes = row["user_notes"] or ""
        if notes:
            if existing_notes:
                combined_notes = (
                    f"{existing_notes}\n{notes}"
                )
            else:
                combined_notes = notes
        else:
            combined_notes = existing_notes or None

        # Update candidate
        cur.execute(
            "UPDATE candidate_review_queue "
            "SET quiet_score = ?, "
            "vibrancy_score = ?, "
            "quiet_gatekeeper_result = ?, "
            "user_notes = ?, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE candidate_id = ?",
            (
                quiet_score,
                vibrancy_score,
                gatekeeper_result,
                combined_notes,
                candidate_id,
            ),
        )
        conn.commit()

        # Also update watched property if promoted
        normalized = row["normalized_address"]
        if normalized:
            cur.execute(
                "SELECT property_id FROM "
                "watched_properties "
                "WHERE normalized_address = ?",
                (normalized,),
            )
            watched = cur.fetchone()
            if watched:
                cur.execute(
                    "UPDATE watched_properties "
                    "SET quiet_score = ?, "
                    "vibrancy_score = ?, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE property_id = ?",
                    (
                        quiet_score,
                        vibrancy_score,
                        watched["property_id"],
                    ),
                )
                conn.commit()

        conn.close()

        result.success = True
        result.detail = (
            f"Quiet={quiet_score}, "
            f"Vibrancy={vibrancy_score}, "
            f"Gatekeeper={gatekeeper_result}"
        )

    except Exception as e:
        result.detail = f"Score update failed: {e}"

    return result


def apply_candidate_noise_notes(
    candidate_id: int,
    noise_risk: str = "unknown",
    noise_sources: Optional[str] = None,
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
) -> OperatorCandidateActionResult:
    """Add noise observation notes to a candidate.

    Records local field knowledge about noise concerns.
    Does not add walkability fields. Does not infer
    seller intent. Does not make purchase recommendations.

    Args:
        candidate_id: Candidate ID.
        noise_risk: Risk level (low/moderate/high/
            severe/unknown).
        noise_sources: Comma-separated noise sources.
        notes: Free-text notes.
        db_path: Path to SQLite database.

    Returns:
        Action result with success status and detail.
    """
    if db_path is None:
        db_path = "data/market_sentry.db"

    result = OperatorCandidateActionResult(
        candidate_id=candidate_id,
        action="noise_notes",
    )

    if noise_risk not in VALID_NOISE_RISKS:
        result.detail = (
            f"Invalid noise risk: {noise_risk}. "
            f"Valid: {', '.join(sorted(VALID_NOISE_RISKS))}"
        )
        return result

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM candidate_review_queue "
            "WHERE candidate_id = ?",
            (candidate_id,),
        )
        row = cur.fetchone()

        if row is None:
            conn.close()
            result.detail = (
                f"Candidate {candidate_id} not found"
            )
            return result

        # Build noise note
        noise_note_parts = [
            f"[Noise observation: risk={noise_risk}]"
        ]
        if noise_sources:
            noise_note_parts.append(
                f"[Sources: {noise_sources}]"
            )
        if notes:
            noise_note_parts.append(notes)

        noise_note = " ".join(noise_note_parts)

        # Append to existing notes
        existing = row["user_notes"] or ""
        if existing:
            combined = f"{existing}\n{noise_note}"
        else:
            combined = noise_note

        cur.execute(
            "UPDATE candidate_review_queue "
            "SET user_notes = ?, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE candidate_id = ?",
            (combined, candidate_id),
        )
        conn.commit()
        conn.close()

        result.success = True
        result.detail = (
            f"Noise notes added: risk={noise_risk}"
        )
        if noise_sources:
            result.detail += f", sources={noise_sources}"

    except Exception as e:
        result.detail = f"Noise notes failed: {e}"

    return result


def build_missing_data_actions(
    db_path: Optional[str] = None,
) -> List[OperatorWorkflowAction]:
    """Build list of missing data actions.

    Identifies candidates that need Quiet/Vibrancy scores,
    price data, or review decisions.

    Args:
        db_path: Path to SQLite database.

    Returns:
        List of recommended actions.
    """
    if db_path is None:
        db_path = "data/market_sentry.db"

    actions: List[OperatorWorkflowAction] = []

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Missing quiet/vibrancy
        cur.execute(
            "SELECT candidate_id, address FROM "
            "candidate_review_queue "
            "WHERE quiet_score IS NULL "
            "OR vibrancy_score IS NULL "
            "ORDER BY candidate_id"
        )
        for row in cur.fetchall():
            actions.append(
                OperatorWorkflowAction(
                    action_id=(
                        f"scores_{row['candidate_id']}"
                    ),
                    description=(
                        f"Enter Quiet/Vibrancy for "
                        f"#{row['candidate_id']}: "
                        f"{row['address']}"
                    ),
                    priority="high",
                    command=(
                        f"marketsentry "
                        f"candidate-location-scores "
                        f"--candidate-id "
                        f"{row['candidate_id']} "
                        f"--quiet-score <value> "
                        f"--vibrancy-score <value>"
                    ),
                )
            )

        # Pending review
        cur.execute(
            "SELECT candidate_id, address FROM "
            "candidate_review_queue "
            "WHERE review_status = 'pending' "
            "AND (beds IS NOT NULL "
            "OR quiet_score IS NOT NULL) "
            "ORDER BY candidate_id"
        )
        for row in cur.fetchall():
            actions.append(
                OperatorWorkflowAction(
                    action_id=(
                        f"review_{row['candidate_id']}"
                    ),
                    description=(
                        f"Review #{row['candidate_id']}: "
                        f"{row['address']}"
                    ),
                    priority="normal",
                    command=(
                        f"marketsentry "
                        f"candidate-decision "
                        f"--candidate-id "
                        f"{row['candidate_id']} "
                        f"--decision <save|reject|maybe>"
                    ),
                )
            )

        conn.close()
    except Exception:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return actions


def export_operator_action_summary(
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
    fmt: str = "both",
) -> List[str]:
    """Export operator action summary.

    Exports candidate status counts, missing data counts,
    recent actions, latest reports, and recommendations.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Path to exports directory.
        fmt: Export format - csv, md, or both.

    Returns:
        List of exported file paths.
    """
    if db_path is None:
        db_path = "data/market_sentry.db"
    if exports_dir is None:
        exports_dir = "data/exports"

    status = build_operator_workflow_status(
        db_path=db_path, exports_dir=exports_dir
    )
    missing = build_missing_data_actions(db_path=db_path)

    out_path = Path(exports_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"operator_action_summary_{ts}"
    paths: List[str] = []

    if fmt in ("md", "both"):
        md_path = out_path / f"{base}.md"
        md_content = _build_action_summary_md(
            status, missing
        )
        md_path.write_text(md_content, encoding="utf-8")
        paths.append(str(md_path))

    if fmt in ("csv", "both"):
        csv_path = out_path / f"{base}.csv"
        csv_content = _build_action_summary_csv(
            status, missing
        )
        csv_path.write_text(
            csv_content, encoding="utf-8"
        )
        paths.append(str(csv_path))

    return paths


# -------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------


def _build_action_summary_md(
    status: OperatorWorkflowStatus,
    missing: List[OperatorWorkflowAction],
) -> str:
    """Build operator action summary Markdown."""
    lines = [
        "# Operator Action Summary",
        "",
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Candidate Status",
        "",
        f"- Total: {status.total_candidates}",
        f"- Pending: {status.pending_candidates}",
        f"- Maybe: {status.maybe_candidates}",
        f"- Saved: {status.saved_candidates}",
        f"- Rejected: {status.rejected_candidates}",
        f"- Hold for more data: {status.hold_candidates}",
        f"- Active watched: {status.active_watched}",
        "",
        "## Missing Data",
        "",
        f"- Missing Quiet/Vibrancy: "
        f"{status.missing_quiet_vibrancy}",
        f"- Missing price: {status.missing_price}",
        f"- Missing enrichment: "
        f"{status.missing_enrichment}",
        f"- Needing review: {status.needing_review}",
        "",
    ]

    if missing:
        lines.append("## Recommended Actions")
        lines.append("")
        for action in missing:
            lines.append(
                f"- [{action.priority}] "
                f"{action.description}"
            )
            lines.append(f"  `{action.command}`")
        lines.append("")

    if status.latest_reports:
        lines.append("## Latest Reports")
        lines.append("")
        for rp in status.latest_reports:
            lines.append(f"- {rp}")
        lines.append("")

    lines.append("## Safety Note")
    lines.append("")
    lines.append(
        "All operations are local-only. No live "
        "retrieval, no outbound notifications, no "
        "browser automation."
    )
    lines.append("")

    return "\n".join(lines)


def _build_action_summary_csv(
    status: OperatorWorkflowStatus,
    missing: List[OperatorWorkflowAction],
) -> str:
    """Build operator action summary CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["section", "item", "value", "detail"]
    )

    writer.writerow(
        ["status", "total_candidates",
         str(status.total_candidates), ""]
    )
    writer.writerow(
        ["status", "pending",
         str(status.pending_candidates), ""]
    )
    writer.writerow(
        ["status", "maybe",
         str(status.maybe_candidates), ""]
    )
    writer.writerow(
        ["status", "saved",
         str(status.saved_candidates), ""]
    )
    writer.writerow(
        ["status", "rejected",
         str(status.rejected_candidates), ""]
    )
    writer.writerow(
        ["status", "hold",
         str(status.hold_candidates), ""]
    )
    writer.writerow(
        ["status", "active_watched",
         str(status.active_watched), ""]
    )
    writer.writerow(
        ["missing", "quiet_vibrancy",
         str(status.missing_quiet_vibrancy), ""]
    )
    writer.writerow(
        ["missing", "price",
         str(status.missing_price), ""]
    )
    writer.writerow(
        ["missing", "enrichment",
         str(status.missing_enrichment), ""]
    )

    for action in missing:
        writer.writerow(
            ["action", action.action_id,
             action.priority, action.description]
        )

    return output.getvalue()
