"""Manual Quiet/Vibrancy score entry and noise-risk capture.

After visually reading a Redfin property page, the operator types the
Quiet and Vibrancy values here. Nothing in this module reads Redfin.
There is no HTTP client, no browser, and no parsing of a live page:
the numbers come from the operator's eyes and keyboard.

This module adds validation, a per-candidate score-entry status, and a
local export so the operator can see exactly which candidates still
need scores and what to do next.

Critical domain rule preserved unchanged: Quiet Score is the
gatekeeper at 7.0. A low Vibrancy score never rescues a Quiet score
below the threshold.

This module does NOT perform live retrieval, browser automation,
outbound notifications, or credential storage, and does not add
walkability fields.
"""

import csv
import io
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.config import config

# Lifestyle scores are read off Redfin on a 0-10 scale.
LIFESTYLE_SCORE_MIN = 0.0
LIFESTYLE_SCORE_MAX = 10.0

# Mirrors operator_workflow.VALID_NOISE_RISKS. Duplicated as a local
# constant would drift, so it is imported at use time instead.
NOISE_RISK_LEVELS = [
    "unknown",
    "low",
    "moderate",
    "high",
    "severe",
]

# Recognized noise sources. The union of the sources already documented
# in the operator workflow and the ones the dashboard offers. Parsing is
# deliberately permissive: unrecognized sources are preserved, because
# local field knowledge should never be silently discarded.
KNOWN_NOISE_SOURCES = [
    "traffic",
    "airport",
    "road",
    "arterial_road",
    "freeway",
    "nighttime_racing",
    "school",
    "commercial",
    "topography",
    "unknown",
    "other",
]

# Tags written into user_notes by apply_candidate_noise_notes.
_NOISE_RISK_PATTERN = re.compile(
    r"\[Noise observation: risk=([a-z_]+)\]",
    re.IGNORECASE,
)
_NOISE_SOURCES_PATTERN = re.compile(
    r"\[Sources: ([^\]]+)\]",
    re.IGNORECASE,
)


class LifestyleScoreValidation(BaseModel):
    """Outcome of validating one manually entered score."""

    is_valid: bool = False
    value: Optional[float] = None
    error_message: str = ""


class NoiseRiskValidation(BaseModel):
    """Outcome of validating a noise risk level."""

    is_valid: bool = False
    value: str = ""
    error_message: str = ""


class GatekeeperExplanation(BaseModel):
    """Plain-language explanation of a gatekeeper outcome."""

    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    threshold: float = 7.0
    result: str = ""
    explanation: str = ""
    vibrancy_note: str = ""
    passes: bool = False


class CandidateScoreEntryStatus(BaseModel):
    """What a single candidate still needs from the operator."""

    candidate_id: int = 0
    address: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    redfin_url: Optional[str] = None
    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    quiet_gatekeeper_result: Optional[str] = None
    noise_risk: Optional[str] = None
    noise_sources: List[str] = Field(default_factory=list)
    user_notes: Optional[str] = None
    needs_quiet_vibrancy: bool = False
    needs_noise_notes: bool = False
    is_gatekeeper_fail: bool = False
    is_watchlisted: bool = False
    missing_fields: List[str] = Field(default_factory=list)
    recommended_next_step: str = ""


class ManualScoreEntryResult(BaseModel):
    """Outcome of a combined score and noise-note entry."""

    candidate_id: int = 0
    success: bool = False
    scores_applied: bool = False
    noise_notes_applied: bool = False
    detail: str = ""
    errors: List[str] = Field(default_factory=list)
    gatekeeper: Optional[GatekeeperExplanation] = None
    refresh_requested: bool = False
    refresh_ran: bool = False
    refresh_output_paths: List[str] = Field(default_factory=list)
    refresh_error: Optional[str] = None


# -------------------------------------------------------------------
# Validation helpers
# -------------------------------------------------------------------


def validate_lifestyle_score(value: Any) -> LifestyleScoreValidation:
    """Validate one manually entered Quiet or Vibrancy score.

    Accepts anything that reads as a number between 0.0 and 10.0
    inclusive. Booleans are rejected because Python treats them as
    ints and ``True`` is not a score an operator meant to type.

    Args:
        value: Raw operator input.

    Returns:
        Validation result with the parsed value or an operator-facing
        error message.
    """
    if value is None or (
        isinstance(value, str) and not value.strip()
    ):
        return LifestyleScoreValidation(
            is_valid=False,
            error_message=(
                "Score is required. Enter a number from 0.0 to 10.0 "
                "as shown on the Redfin page."
            ),
        )

    if isinstance(value, bool):
        return LifestyleScoreValidation(
            is_valid=False,
            error_message=(
                f"'{value}' is not a score. Enter a number from "
                "0.0 to 10.0."
            ),
        )

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return LifestyleScoreValidation(
            is_valid=False,
            error_message=(
                f"'{value}' is not a number. Enter a number from "
                "0.0 to 10.0, for example 9.9."
            ),
        )

    if parsed != parsed or parsed in (
        float("inf"),
        float("-inf"),
    ):
        return LifestyleScoreValidation(
            is_valid=False,
            error_message=(
                "Score must be a real number from 0.0 to 10.0."
            ),
        )

    if parsed < LIFESTYLE_SCORE_MIN or parsed > LIFESTYLE_SCORE_MAX:
        return LifestyleScoreValidation(
            is_valid=False,
            error_message=(
                f"Score {parsed} is outside the valid range "
                f"{LIFESTYLE_SCORE_MIN} to {LIFESTYLE_SCORE_MAX}. "
                "Redfin lifestyle scores are on a 0-10 scale."
            ),
        )

    return LifestyleScoreValidation(is_valid=True, value=parsed)


def validate_noise_risk(value: Any) -> NoiseRiskValidation:
    """Validate a noise risk level.

    Args:
        value: Raw operator input.

    Returns:
        Validation result with the normalized level or an error.
    """
    from marketsentry.operator_workflow import VALID_NOISE_RISKS

    if value is None or (
        isinstance(value, str) and not value.strip()
    ):
        return NoiseRiskValidation(
            is_valid=True,
            value="unknown",
        )

    normalized = str(value).strip().lower()
    if normalized not in VALID_NOISE_RISKS:
        return NoiseRiskValidation(
            is_valid=False,
            value=normalized,
            error_message=(
                f"'{value}' is not a noise risk level. Valid levels: "
                f"{', '.join(sorted(VALID_NOISE_RISKS))}."
            ),
        )

    return NoiseRiskValidation(is_valid=True, value=normalized)


def parse_noise_sources(value: Any) -> List[str]:
    """Parse a comma-separated noise source list.

    Normalizes spacing and case and removes duplicates while keeping
    the operator's ordering. Unrecognized sources are kept, not
    dropped: local field knowledge is the point of this field.

    Args:
        value: Raw operator input, for example "traffic, airport".

    Returns:
        Normalized source list, empty when nothing was supplied.
    """
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        raw_parts = [str(v) for v in value]
    else:
        raw_parts = str(value).split(",")

    sources: List[str] = []
    for part in raw_parts:
        cleaned = part.strip().lower().replace(" ", "_")
        if not cleaned:
            continue
        if cleaned not in sources:
            sources.append(cleaned)

    return sources


def build_gatekeeper_explanation(
    quiet_score: Optional[float],
    vibrancy_score: Optional[float] = None,
) -> GatekeeperExplanation:
    """Explain a gatekeeper outcome in plain language.

    Delegates the decision itself to the existing gatekeeper so this
    function can never drift from the rule it describes.

    Args:
        quiet_score: Quiet score, higher is quieter.
        vibrancy_score: Vibrancy score, lower is calmer.

    Returns:
        Explanation including why low Vibrancy cannot rescue a Quiet
        score below the threshold.
    """
    from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper

    result, _reason = apply_quiet_gatekeeper(
        quiet_score, vibrancy_score
    )
    threshold = config.quiet_score_minimum

    explanation = GatekeeperExplanation(
        quiet_score=quiet_score,
        vibrancy_score=vibrancy_score,
        threshold=threshold,
        result=result,
        passes=(result == "pass"),
    )

    if result == "fail_no_data":
        explanation.explanation = (
            "No Quiet score recorded yet, so the gatekeeper cannot "
            "be applied. Read the Quiet score from the Redfin page "
            "and enter it."
        )
        explanation.vibrancy_note = (
            "Vibrancy alone cannot decide this candidate."
        )
        return explanation

    if result == "fail_noise_risk":
        explanation.explanation = (
            f"Quiet {quiet_score} is below the {threshold} "
            "gatekeeper threshold, so this candidate is marked "
            "fail_noise_risk"
        )
        if vibrancy_score is not None:
            explanation.explanation += (
                f" even though Vibrancy is {vibrancy_score}."
            )
            explanation.vibrancy_note = (
                f"Vibrancy {vibrancy_score} is low, but low Vibrancy "
                "does not override a Quiet failure. Quiet is the "
                "gatekeeper."
            )
        else:
            explanation.explanation += "."
            explanation.vibrancy_note = (
                "Low Vibrancy does not override a Quiet failure."
            )
        return explanation

    explanation.explanation = (
        f"Quiet {quiet_score} meets the {threshold} gatekeeper "
        "threshold, so this candidate passes."
    )
    if vibrancy_score is not None:
        explanation.vibrancy_note = (
            f"Vibrancy {vibrancy_score} is recorded for location "
            "fit, but it is not a gatekeeper."
        )
    return explanation


# -------------------------------------------------------------------
# Candidate score-entry status
# -------------------------------------------------------------------


def extract_noise_risk_from_notes(
    notes: Optional[str],
) -> Optional[str]:
    """Read the most recent noise risk tag out of a notes field."""
    if not notes:
        return None
    matches = _NOISE_RISK_PATTERN.findall(notes)
    return matches[-1].lower() if matches else None


def extract_noise_sources_from_notes(
    notes: Optional[str],
) -> List[str]:
    """Read the most recent noise source tag out of a notes field."""
    if not notes:
        return []
    matches = _NOISE_SOURCES_PATTERN.findall(notes)
    if not matches:
        return []
    return parse_noise_sources(matches[-1])


def _recommended_next_step(
    status: CandidateScoreEntryStatus,
) -> str:
    """Derive the next data-gathering step for one candidate."""
    if status.needs_quiet_vibrancy:
        return (
            "Open the Redfin page, visually read Quiet and Vibrancy, "
            "then enter both scores."
        )
    if status.is_gatekeeper_fail and status.needs_noise_notes:
        return (
            "Fails the Quiet gatekeeper. Record local noise "
            "knowledge, then hold or reject as a noise-risk control."
        )
    if status.is_gatekeeper_fail:
        return (
            "Fails the Quiet gatekeeper. Hold or reject as a "
            "noise-risk control."
        )
    if status.needs_noise_notes:
        return (
            "Scores recorded. Add local noise knowledge if you have "
            "any for this location."
        )
    if not status.is_watchlisted:
        return "Scores recorded. Record a candidate decision."
    return "Scores recorded and watchlisted. No score entry needed."


def _row_to_status(
    row: sqlite3.Row,
    watchlisted_addresses: set,
) -> CandidateScoreEntryStatus:
    """Convert a candidate row into a score-entry status."""
    notes = row["user_notes"]
    noise_risk = extract_noise_risk_from_notes(notes)

    status = CandidateScoreEntryStatus(
        candidate_id=row["candidate_id"],
        address=row["address"],
        city=row["city"],
        zip=row["zip"],
        redfin_url=row["redfin_url"],
        quiet_score=row["quiet_score"],
        vibrancy_score=row["vibrancy_score"],
        quiet_gatekeeper_result=row["quiet_gatekeeper_result"],
        noise_risk=noise_risk,
        noise_sources=extract_noise_sources_from_notes(notes),
        user_notes=notes,
    )

    missing: List[str] = []
    if status.quiet_score is None:
        missing.append("quiet_score")
    if status.vibrancy_score is None:
        missing.append("vibrancy_score")
    if noise_risk is None:
        missing.append("noise_risk")

    status.missing_fields = missing
    status.needs_quiet_vibrancy = (
        status.quiet_score is None
        or status.vibrancy_score is None
    )
    status.needs_noise_notes = noise_risk is None
    status.is_gatekeeper_fail = (
        status.quiet_gatekeeper_result == "fail_noise_risk"
    )
    normalized = row["normalized_address"]
    status.is_watchlisted = bool(
        normalized and normalized in watchlisted_addresses
    )
    status.recommended_next_step = _recommended_next_step(status)

    return status


def _watchlisted_addresses(conn: sqlite3.Connection) -> set:
    """Collect normalized addresses already on the watchlist."""
    exists = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='watched_properties'"
    ).fetchone()
    if not exists:
        return set()

    rows = conn.execute(
        "SELECT normalized_address FROM watched_properties"
    ).fetchall()
    return {r[0] for r in rows if r[0]}


def build_candidate_score_entry_status(
    candidate_id: int,
    db_path: Optional[str] = None,
) -> Optional[CandidateScoreEntryStatus]:
    """Build the score-entry status for one candidate.

    Read-only. Performs no mutation and no live retrieval.

    Args:
        candidate_id: Candidate ID.
        db_path: Path to SQLite database.

    Returns:
        Status, or None when the candidate does not exist.
    """
    path = db_path or config.database_path
    if not Path(path).exists():
        return None

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM candidate_review_queue "
            "WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_status(row, _watchlisted_addresses(conn))
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def list_candidate_score_entry_statuses(
    db_path: Optional[str] = None,
) -> List[CandidateScoreEntryStatus]:
    """Build score-entry statuses for every candidate.

    Args:
        db_path: Path to SQLite database.

    Returns:
        Statuses ordered by candidate ID.
    """
    path = db_path or config.database_path
    if not Path(path).exists():
        return []

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        watchlisted = _watchlisted_addresses(conn)
        rows = conn.execute(
            "SELECT * FROM candidate_review_queue "
            "ORDER BY candidate_id"
        ).fetchall()
        return [_row_to_status(r, watchlisted) for r in rows]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def list_candidates_needing_scores(
    db_path: Optional[str] = None,
    include_missing_noise_notes: bool = False,
) -> List[CandidateScoreEntryStatus]:
    """List candidates still needing manual score entry.

    Args:
        db_path: Path to SQLite database.
        include_missing_noise_notes: Also include candidates that
            have scores but no recorded noise observation.

    Returns:
        Candidates needing operator attention.
    """
    statuses = list_candidate_score_entry_statuses(db_path=db_path)
    if include_missing_noise_notes:
        return [
            s
            for s in statuses
            if s.needs_quiet_vibrancy or s.needs_noise_notes
        ]
    return [s for s in statuses if s.needs_quiet_vibrancy]


def list_candidates_failing_gatekeeper(
    db_path: Optional[str] = None,
) -> List[CandidateScoreEntryStatus]:
    """List candidates whose Quiet score fails the gatekeeper."""
    return [
        s
        for s in list_candidate_score_entry_statuses(db_path=db_path)
        if s.is_gatekeeper_fail
    ]


# -------------------------------------------------------------------
# Combined manual entry
# -------------------------------------------------------------------


def apply_scores_and_noise_notes(
    candidate_id: int,
    quiet_score: Any = None,
    vibrancy_score: Any = None,
    noise_risk: Optional[str] = None,
    noise_sources: Optional[str] = None,
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
    refresh: bool = False,
    exports_dir: Optional[str] = None,
) -> ManualScoreEntryResult:
    """Apply scores and noise notes in one operator action.

    Validates first and applies nothing when validation fails, so a
    typo cannot write a partial update. Scores and noise notes are
    each optional; supply either or both.

    Delegates the writes to the existing operator workflow actions so
    gatekeeper handling and note appending stay identical to the
    single-purpose commands.

    Args:
        candidate_id: Candidate ID.
        quiet_score: Quiet score read off the Redfin page.
        vibrancy_score: Vibrancy score read off the Redfin page.
        noise_risk: Noise risk level.
        noise_sources: Comma-separated noise sources.
        notes: Free-text local knowledge.
        db_path: Path to SQLite database.
        refresh: Run the local refresh workflow afterwards.
        exports_dir: Exports directory used when refreshing.

    Returns:
        Result describing what was applied.
    """
    from marketsentry.operator_workflow import (
        apply_candidate_location_scores,
        apply_candidate_noise_notes,
    )

    path = db_path or config.database_path
    result = ManualScoreEntryResult(candidate_id=candidate_id)

    wants_scores = (
        quiet_score is not None or vibrancy_score is not None
    )
    wants_noise = bool(noise_risk or noise_sources or notes)

    if not wants_scores and not wants_noise:
        result.errors.append(
            "Nothing to apply. Supply scores, noise notes, or both."
        )
        result.detail = "No changes requested."
        return result

    # Validate everything before writing anything.
    quiet_value: Optional[float] = None
    vibrancy_value: Optional[float] = None

    if wants_scores:
        if quiet_score is None or vibrancy_score is None:
            result.errors.append(
                "Enter both Quiet and Vibrancy together so the "
                "gatekeeper is applied to a complete pair."
            )
        else:
            quiet_check = validate_lifestyle_score(quiet_score)
            if not quiet_check.is_valid:
                result.errors.append(
                    f"Quiet score: {quiet_check.error_message}"
                )
            else:
                quiet_value = quiet_check.value

            vibrancy_check = validate_lifestyle_score(
                vibrancy_score
            )
            if not vibrancy_check.is_valid:
                result.errors.append(
                    f"Vibrancy score: "
                    f"{vibrancy_check.error_message}"
                )
            else:
                vibrancy_value = vibrancy_check.value

    risk_value = "unknown"
    if wants_noise:
        risk_check = validate_noise_risk(noise_risk)
        if not risk_check.is_valid:
            result.errors.append(risk_check.error_message)
        else:
            risk_value = risk_check.value

    if result.errors:
        result.detail = (
            "Validation failed. No changes were applied."
        )
        return result

    existing = build_candidate_score_entry_status(
        candidate_id, db_path=path
    )
    if existing is None:
        result.errors.append(
            f"Candidate {candidate_id} not found."
        )
        result.detail = "Candidate not found."
        return result

    details: List[str] = []

    if quiet_value is not None and vibrancy_value is not None:
        score_result = apply_candidate_location_scores(
            candidate_id=candidate_id,
            quiet_score=quiet_value,
            vibrancy_score=vibrancy_value,
            db_path=path,
        )
        result.scores_applied = score_result.success
        if score_result.success:
            details.append(score_result.detail)
            result.gatekeeper = build_gatekeeper_explanation(
                quiet_value, vibrancy_value
            )
        else:
            result.errors.append(score_result.detail)

    if wants_noise:
        parsed_sources = parse_noise_sources(noise_sources)
        noise_result = apply_candidate_noise_notes(
            candidate_id=candidate_id,
            noise_risk=risk_value,
            noise_sources=(
                ",".join(parsed_sources)
                if parsed_sources
                else None
            ),
            notes=notes,
            db_path=path,
        )
        result.noise_notes_applied = noise_result.success
        if noise_result.success:
            details.append(noise_result.detail)
        else:
            result.errors.append(noise_result.detail)

    result.success = (
        result.scores_applied or result.noise_notes_applied
    ) and not result.errors
    result.detail = (
        "; ".join(details) if details else "No changes applied."
    )

    result.refresh_requested = refresh
    if refresh and result.success:
        try:
            from marketsentry.operator_workflow import (
                run_operator_refresh_workflow,
            )

            run_result = run_operator_refresh_workflow(
                db_path=path,
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


# -------------------------------------------------------------------
# Export
# -------------------------------------------------------------------


def export_manual_score_entry_queue(
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
    fmt: str = "both",
    include_complete: bool = False,
) -> List[str]:
    """Export the manual score entry queue to CSV and/or Markdown.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Path to exports directory.
        fmt: Export format - csv, md, or both.
        include_complete: Include candidates that need nothing.

    Returns:
        List of exported file paths.
    """
    path = db_path or config.database_path
    out_dir = exports_dir or config.data_exports_dir

    statuses = list_candidate_score_entry_statuses(db_path=path)
    if not include_complete:
        statuses = [
            s
            for s in statuses
            if s.needs_quiet_vibrancy
            or s.needs_noise_notes
            or s.is_gatekeeper_fail
        ]

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"manual_score_entry_queue_{timestamp}"
    paths: List[str] = []

    if fmt in ("md", "both"):
        md_path = out_path / f"{base}.md"
        md_path.write_text(
            _build_queue_md(statuses), encoding="utf-8"
        )
        paths.append(str(md_path))

    if fmt in ("csv", "both"):
        csv_path = out_path / f"{base}.csv"
        csv_path.write_text(
            _build_queue_csv(statuses), encoding="utf-8"
        )
        paths.append(str(csv_path))

    return paths


def _build_queue_md(
    statuses: List[CandidateScoreEntryStatus],
) -> str:
    """Build the manual score entry queue Markdown report."""
    lines = [
        "# Manual Score Entry Queue",
        "",
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Candidates listed: {len(statuses)}",
        "",
        "Quiet Score is the gatekeeper at "
        f"{config.quiet_score_minimum}. A low Vibrancy score does "
        "not override a Quiet score below the threshold.",
        "",
    ]

    if not statuses:
        lines.append(
            "No candidates need manual score entry."
        )
        lines.append("")
        return "\n".join(lines)

    lines.append("## Candidates")
    lines.append("")
    lines.append(
        "| ID | Address | City | ZIP | Quiet | Vibrancy | "
        "Gatekeeper | Noise Risk | Noise Sources | Missing | "
        "Next Step | Redfin Link |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|---|---|---|"
    )

    for status in statuses:
        link = (
            f"[View]({status.redfin_url})"
            if status.redfin_url
            else ""
        )
        lines.append(
            f"| {status.candidate_id} "
            f"| {status.address or ''} "
            f"| {status.city or ''} "
            f"| {status.zip or ''} "
            f"| {_fmt(status.quiet_score)} "
            f"| {_fmt(status.vibrancy_score)} "
            f"| {status.quiet_gatekeeper_result or ''} "
            f"| {status.noise_risk or ''} "
            f"| {','.join(status.noise_sources)} "
            f"| {','.join(status.missing_fields)} "
            f"| {status.recommended_next_step} "
            f"| {link} |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for status in statuses:
        if status.user_notes:
            lines.append(
                f"### Candidate {status.candidate_id} - "
                f"{status.address or ''}"
            )
            lines.append("")
            lines.append("```text")
            lines.append(status.user_notes)
            lines.append("```")
            lines.append("")

    lines.append("## Safety Note")
    lines.append("")
    lines.append(
        "Scores are entered manually by the operator after "
        "visually reading the Redfin page. Nothing here reads "
        "Redfin. No live retrieval, no browser automation, no "
        "outbound notifications. This report is analytical "
        "guidance, not a purchase recommendation."
    )
    lines.append("")

    return "\n".join(lines)


def _build_queue_csv(
    statuses: List[CandidateScoreEntryStatus],
) -> str:
    """Build the manual score entry queue CSV report."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "candidate_id",
        "address",
        "city",
        "zip",
        "quiet_score",
        "vibrancy_score",
        "quiet_gatekeeper_result",
        "noise_risk",
        "noise_sources",
        "needs_quiet_vibrancy",
        "needs_noise_notes",
        "is_gatekeeper_fail",
        "is_watchlisted",
        "missing_fields",
        "recommended_next_step",
        "redfin_url",
        "user_notes",
    ])

    for status in statuses:
        writer.writerow([
            status.candidate_id,
            status.address or "",
            status.city or "",
            status.zip or "",
            _fmt(status.quiet_score),
            _fmt(status.vibrancy_score),
            status.quiet_gatekeeper_result or "",
            status.noise_risk or "",
            ",".join(status.noise_sources),
            "yes" if status.needs_quiet_vibrancy else "no",
            "yes" if status.needs_noise_notes else "no",
            "yes" if status.is_gatekeeper_fail else "no",
            "yes" if status.is_watchlisted else "no",
            ",".join(status.missing_fields),
            status.recommended_next_step,
            status.redfin_url or "",
            status.user_notes or "",
        ])

    return output.getvalue()


def _fmt(value: Optional[float]) -> str:
    """Format an optional score for report output."""
    return "" if value is None else str(value)


def summarize_manual_score_entry_queue(
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Summarize outstanding manual score entry work."""
    statuses = list_candidate_score_entry_statuses(db_path=db_path)
    return {
        "total_candidates": len(statuses),
        "needing_quiet_vibrancy": len(
            [s for s in statuses if s.needs_quiet_vibrancy]
        ),
        "needing_noise_notes": len(
            [s for s in statuses if s.needs_noise_notes]
        ),
        "failing_gatekeeper": len(
            [s for s in statuses if s.is_gatekeeper_fail]
        ),
        "watchlisted": len(
            [s for s in statuses if s.is_watchlisted]
        ),
    }
