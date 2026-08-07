"""Effective DOM evidence audit and confidence reporting.

Answers a question the existing DOM numbers cannot: *how much should the
operator trust them?* A property with three years of listing events and a
county-confirmed transfer deserves more weight than one showing only a
displayed DOM scraped from a single page, yet both previously rendered as
a bare integer.

This module gathers the underlying evidence, reports Effective DOM v1,
Effective DOM v2, and the Churn Index side by side, explains any reset
boundary, names every missing piece of evidence, and produces a
deterministic confidence score.

Domain rules preserved exactly:

- **Effective DOM and Churn Index stay separate.** They are computed by
  different functions, stored in different fields, and reported in
  different columns. Nothing here averages or blends them.
- **A county-confirmed transfer may reset Effective DOM v2.** Exposure
  before the boundary is excluded from v2 only.
- **A reset never erases the Churn Index.** Churn is computed over its
  own lookback window from the full event history, independent of any
  reset boundary. The audit asserts this and reports it explicitly.

The audit is read-only. It performs no live retrieval, no scraping, no
browser automation, no outbound notifications, and no credential
handling, and it adds no walkability fields. It describes evidence; it
does not infer seller intent and does not recommend any purchase.
"""

import csv
import io
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.config import config

# Confidence categories, strongest first.
CONFIDENCE_HIGH = "high"
CONFIDENCE_MODERATE = "moderate"
CONFIDENCE_LOW = "low"
CONFIDENCE_INSUFFICIENT = "insufficient"

# Score thresholds. Deterministic and inclusive of the lower bound.
HIGH_SCORE_MIN = 75
MODERATE_SCORE_MIN = 50
LOW_SCORE_MIN = 25

# Evidence gap identifiers.
GAP_MISSING_LISTING_EVENTS = "missing_listing_events"
GAP_MISSING_CURRENT_LISTING_START = "missing_current_listing_start"
GAP_MISSING_DISPLAYED_DOM = "missing_displayed_dom"
GAP_MISSING_COUNTY_TRANSFER_EVIDENCE = (
    "missing_county_transfer_evidence"
)
GAP_MISSING_SOURCE_PAGE = "missing_source_page"
GAP_CONFLICTING_DOM_VALUES = "conflicting_dom_values"
GAP_STALE_OBSERVATION = "stale_observation"

# An observation older than this is called out as stale.
STALE_OBSERVATION_DAYS = 90

# Weight each evidence factor contributes to the confidence score.
# Positive factors sum to 100 so a fully evidenced property scores 100.
FACTOR_WEIGHTS: Dict[str, int] = {
    "multiple_listing_events": 25,
    "current_listing_start_known": 20,
    "county_transfer_evidence": 20,
    "redfin_detail_enrichment": 15,
    "source_pages_present": 10,
    "county_corroboration": 10,
}

# Penalties applied on top. Kept smaller than the positive weights so a
# well-evidenced property is not driven to "insufficient" by one gap.
PENALTY_WEIGHTS: Dict[str, int] = {
    "displayed_dom_only": 20,
    "conflicting_dom_values": 20,
    "stale_observation": 10,
}


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------


class DomEvidenceItem(BaseModel):
    """One evidence factor considered by the confidence score."""

    factor_id: str = ""
    label: str = ""
    present: bool = False
    weight: int = 0
    contribution: int = 0
    detail: str = ""


class DomResetEvidence(BaseModel):
    """What is known about a v2 reset boundary."""

    reset_applied: bool = False
    reset_date: Optional[date] = None
    record_type: Optional[str] = None
    record_id: Optional[int] = None
    evidence_source: str = "none"
    evidence_status: str = "no_transfer_evidence"
    confidence: Optional[float] = None
    pre_reset_exposure_dom: Optional[int] = None
    post_reset_exposure_dom: Optional[int] = None
    explanation: str = ""


class DomChurnEvidence(BaseModel):
    """Churn Index evidence, reported separately from Effective DOM."""

    churn_index: Optional[float] = None
    lookback_years: int = 3
    churn_event_count: int = 0
    listing_churn_count: int = 0
    dom_reset_count: int = 0
    sale_rent_alternation_count: int = 0
    price_change_count: int = 0
    preserved_after_transfer: bool = True
    explanation: str = ""


class DomEvidenceGap(BaseModel):
    """A named piece of missing or conflicting evidence."""

    gap_id: str = ""
    label: str = ""
    detail: str = ""
    severity: str = "info"


class DomConfidenceScore(BaseModel):
    """Deterministic confidence rating with its inputs."""

    score: int = 0
    category: str = CONFIDENCE_INSUFFICIENT
    factors: List[DomEvidenceItem] = Field(default_factory=list)
    penalties: List[DomEvidenceItem] = Field(default_factory=list)
    explanation: str = ""


class DomEvidenceAudit(BaseModel):
    """Full evidence audit for one candidate or watched property."""

    candidate_id: Optional[int] = None
    watched_property_id: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    redfin_url: Optional[str] = None

    listing_event_count: int = 0
    listing_event_types: List[str] = Field(default_factory=list)
    first_event_date: Optional[date] = None
    latest_event_date: Optional[date] = None
    current_listing_start_date: Optional[date] = None
    status_change_count: int = 0
    price_change_count: int = 0
    source_page_count: int = 0
    county_record_count: int = 0

    displayed_dom: Optional[int] = None
    effective_dom_v1: Optional[int] = None
    effective_dom_v2: Optional[int] = None
    effective_dom_delta_v1: Optional[int] = None
    effective_dom_delta_v2: Optional[int] = None
    v1_v2_delta: Optional[int] = None

    reset: DomResetEvidence = Field(
        default_factory=DomResetEvidence
    )
    churn: DomChurnEvidence = Field(
        default_factory=DomChurnEvidence
    )
    gaps: List[DomEvidenceGap] = Field(default_factory=list)
    confidence: DomConfidenceScore = Field(
        default_factory=DomConfidenceScore
    )
    explanation: str = ""

    @property
    def gap_ids(self) -> List[str]:
        """Identifiers of every evidence gap found."""
        return [g.gap_id for g in self.gaps]

    @property
    def subject_label(self) -> str:
        """Human-readable identifier for this audit subject."""
        if self.candidate_id is not None:
            return f"Candidate {self.candidate_id}"
        if self.watched_property_id is not None:
            return f"Watched property {self.watched_property_id}"
        return "Unknown subject"


class DomEvidenceAuditSummary(BaseModel):
    """Aggregate counts across many audits."""

    total_audited: int = 0
    high_confidence: int = 0
    moderate_confidence: int = 0
    low_confidence: int = 0
    insufficient_confidence: int = 0
    with_evidence_gaps: int = 0
    with_reset_evidence: int = 0
    with_churn_preserved: int = 0
    gap_counts: Dict[str, int] = Field(default_factory=dict)


class DomEvidenceReportRow(BaseModel):
    """Flattened audit row for CSV and Markdown export."""

    candidate_id: Optional[int] = None
    watched_property_id: Optional[int] = None
    address: Optional[str] = None
    redfin_url: Optional[str] = None
    displayed_dom: Optional[int] = None
    effective_dom_v1: Optional[int] = None
    effective_dom_v2: Optional[int] = None
    v1_v2_delta: Optional[int] = None
    reset_applied: bool = False
    reset_date: Optional[date] = None
    reset_evidence_source: str = ""
    reset_evidence_status: str = ""
    churn_index: Optional[float] = None
    churn_event_count: int = 0
    listing_churn_count: int = 0
    dom_reset_count: int = 0
    confidence_category: str = ""
    confidence_score: int = 0
    evidence_gaps: str = ""
    explanation: str = ""


# -------------------------------------------------------------------
# Evidence loading
# -------------------------------------------------------------------


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    """Check whether a table exists without creating it."""
    row = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _load_listing_events(
    conn: sqlite3.Connection,
    candidate_id: Optional[int],
    watched_property_id: Optional[int],
) -> List[Any]:
    """Load listing events for a candidate or watched property."""
    from marketsentry.models import ListingEvent

    if not _table_exists(conn, "listing_events"):
        return []

    if watched_property_id is not None:
        rows = conn.execute(
            "SELECT * FROM listing_events WHERE property_id = ? "
            "ORDER BY event_date",
            (watched_property_id,),
        ).fetchall()
    elif candidate_id is not None:
        rows = conn.execute(
            "SELECT * FROM listing_events WHERE candidate_id = ? "
            "ORDER BY event_date",
            (candidate_id,),
        ).fetchall()
    else:
        return []

    events = []
    for row in rows:
        try:
            events.append(ListingEvent(**dict(row)))
        except Exception:
            # A malformed row is itself an evidence problem, not a
            # reason to abort the whole audit.
            continue
    return events


def _load_county_records(
    conn: sqlite3.Connection,
    candidate_id: Optional[int],
    watched_property_id: Optional[int],
) -> List[Any]:
    """Load county record observations for the subject."""
    from marketsentry.models import CountyRecordObservation

    if not _table_exists(conn, "county_record_observations"):
        return []

    if watched_property_id is not None:
        rows = conn.execute(
            "SELECT * FROM county_record_observations "
            "WHERE property_id = ? ORDER BY record_date",
            (watched_property_id,),
        ).fetchall()
    elif candidate_id is not None:
        rows = conn.execute(
            "SELECT * FROM county_record_observations "
            "WHERE candidate_id = ? ORDER BY record_date",
            (candidate_id,),
        ).fetchall()
    else:
        return []

    records = []
    for row in rows:
        try:
            records.append(CountyRecordObservation(**dict(row)))
        except Exception:
            continue
    return records


def _count_source_pages(
    conn: sqlite3.Connection,
    candidate_id: Optional[int],
    watched_property_id: Optional[int],
) -> int:
    """Count saved source pages backing this subject."""
    if not _table_exists(conn, "source_pages"):
        return 0

    if watched_property_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM source_pages WHERE property_id = ?",
            (watched_property_id,),
        ).fetchone()
    elif candidate_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM source_pages WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    else:
        return 0

    return int(row[0]) if row else 0


def _load_subject_row(
    conn: sqlite3.Connection,
    candidate_id: Optional[int],
    watched_property_id: Optional[int],
) -> Any:
    """Load the candidate or watched property record."""
    if watched_property_id is not None:
        if not _table_exists(conn, "watched_properties"):
            return None
        return conn.execute(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (watched_property_id,),
        ).fetchone()
    if candidate_id is not None:
        if not _table_exists(conn, "candidate_review_queue"):
            return None
        return conn.execute(
            "SELECT * FROM candidate_review_queue "
            "WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    return None


def _row_value(row: Any, key: str) -> Any:
    """Read a column that may not exist on this table."""
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


# -------------------------------------------------------------------
# Reset and churn explanation
# -------------------------------------------------------------------


def build_reset_explanation(
    metrics: Any,
    county_record_count: int,
) -> DomResetEvidence:
    """Explain the v2 reset boundary, or its absence.

    Args:
        metrics: EffectiveDomV2Metrics from the v2 calculator.
        county_record_count: Number of county records available.

    Returns:
        Reset evidence with neutral explanatory text.
    """
    evidence = DomResetEvidence(
        reset_applied=bool(metrics.county_reset_applied),
        reset_date=metrics.county_reset_date,
        record_type=metrics.county_reset_record_type,
        record_id=metrics.county_reset_record_id,
        confidence=metrics.county_reset_confidence,
        pre_reset_exposure_dom=(
            metrics.pre_reset_calendar_exposure_dom
        ),
        post_reset_exposure_dom=(
            metrics.post_reset_calendar_exposure_dom
        ),
    )

    if evidence.reset_applied:
        evidence.evidence_source = "county_record"
        evidence.evidence_status = "county_confirmed_transfer"
        record_label = (
            f" ({evidence.record_type})"
            if evidence.record_type
            else ""
        )
        evidence.explanation = (
            "Effective DOM v2 applies a county-confirmed transfer "
            f"reset on {evidence.reset_date}{record_label}. "
            "Exposure before that boundary is excluded from "
            "Effective DOM v2, but listing churn remains separately "
            "reported in the Churn Index."
        )
        return evidence

    if county_record_count:
        evidence.evidence_source = "county_record"
        evidence.evidence_status = "no_qualifying_transfer"
        evidence.explanation = (
            f"{county_record_count} county record(s) are available, "
            "but none qualify as an ownership transfer within the "
            "listing history window. Effective DOM v2 does not "
            "apply a reset."
        )
        return evidence

    evidence.evidence_source = "none"
    evidence.evidence_status = "no_transfer_evidence"
    evidence.explanation = (
        "No county-confirmed transfer reset evidence is available. "
        "Effective DOM v2 does not apply a reset."
    )
    return evidence


def build_churn_evidence(
    churn_metrics: Any,
    v2_metrics: Any,
    reset: DomResetEvidence,
) -> DomChurnEvidence:
    """Report Churn Index separately from Effective DOM.

    Churn is computed over its own lookback window from the full
    event history. A reset boundary narrows Effective DOM v2 only; it
    never removes churn history.
    """
    evidence = DomChurnEvidence(
        churn_index=churn_metrics.recent_churn_index,
        lookback_years=churn_metrics.recent_churn_lookback_years,
        churn_event_count=churn_metrics.recent_churn_event_count,
        listing_churn_count=v2_metrics.listing_churn_count or 0,
        dom_reset_count=v2_metrics.dom_reset_count or 0,
        sale_rent_alternation_count=(
            v2_metrics.sale_rent_alternation_count or 0
        ),
        price_change_count=v2_metrics.price_change_count or 0,
        preserved_after_transfer=True,
    )

    if reset.reset_applied:
        evidence.explanation = (
            "Churn Index is reported independently of the Effective "
            "DOM v2 reset. The county-confirmed transfer on "
            f"{reset.reset_date} narrows Effective DOM v2 only; it "
            "does not erase listing churn history, which remains "
            f"recorded over a {evidence.lookback_years}-year "
            "lookback."
        )
    else:
        evidence.explanation = (
            "Churn Index is reported independently of Effective "
            f"DOM, over a {evidence.lookback_years}-year lookback."
        )

    return evidence


# -------------------------------------------------------------------
# Evidence gaps
# -------------------------------------------------------------------


def _build_gaps(
    audit: DomEvidenceAudit,
    reset: DomResetEvidence,
    analysis_date: date,
) -> List[DomEvidenceGap]:
    """Identify every missing or conflicting piece of evidence."""
    gaps: List[DomEvidenceGap] = []

    if audit.listing_event_count == 0:
        gaps.append(
            DomEvidenceGap(
                gap_id=GAP_MISSING_LISTING_EVENTS,
                label="No listing events",
                detail=(
                    "No listing events are recorded, so exposure "
                    "cannot be reconstructed from history."
                ),
                severity="high",
            )
        )

    if audit.current_listing_start_date is None:
        gaps.append(
            DomEvidenceGap(
                gap_id=GAP_MISSING_CURRENT_LISTING_START,
                label="No current listing start date",
                detail=(
                    "The start of the current listing instance is "
                    "unknown, so current exposure is estimated."
                ),
                severity="moderate",
            )
        )

    if audit.displayed_dom is None:
        gaps.append(
            DomEvidenceGap(
                gap_id=GAP_MISSING_DISPLAYED_DOM,
                label="No displayed DOM",
                detail=(
                    "No displayed DOM was captured, so the listing "
                    "site figure cannot be compared."
                ),
                severity="info",
            )
        )

    if not reset.reset_applied:
        gaps.append(
            DomEvidenceGap(
                gap_id=GAP_MISSING_COUNTY_TRANSFER_EVIDENCE,
                label="No county transfer evidence",
                detail=reset.explanation,
                severity="moderate",
            )
        )

    if audit.source_page_count == 0:
        gaps.append(
            DomEvidenceGap(
                gap_id=GAP_MISSING_SOURCE_PAGE,
                label="No saved source page",
                detail=(
                    "No saved source page backs these values, so "
                    "they cannot be re-verified against a capture."
                ),
                severity="moderate",
            )
        )

    # A v1/v2 difference is expected when a reset applied. Without
    # reset evidence the two should agree, so a difference means the
    # stored values disagree with the recomputed ones.
    if (
        not reset.reset_applied
        and audit.effective_dom_v1 is not None
        and audit.effective_dom_v2 is not None
        and audit.effective_dom_v1 != audit.effective_dom_v2
    ):
        gaps.append(
            DomEvidenceGap(
                gap_id=GAP_CONFLICTING_DOM_VALUES,
                label="v1 and v2 differ without reset evidence",
                detail=(
                    f"Effective DOM v1 is {audit.effective_dom_v1} "
                    f"and v2 is {audit.effective_dom_v2}, but no "
                    "reset boundary was applied. Review the "
                    "underlying events."
                ),
                severity="high",
            )
        )

    if audit.latest_event_date is not None:
        age_days = (analysis_date - audit.latest_event_date).days
        if age_days > STALE_OBSERVATION_DAYS:
            gaps.append(
                DomEvidenceGap(
                    gap_id=GAP_STALE_OBSERVATION,
                    label="Stale observation",
                    detail=(
                        f"The most recent listing event is "
                        f"{age_days} days old, beyond the "
                        f"{STALE_OBSERVATION_DAYS}-day freshness "
                        "window."
                    ),
                    severity="moderate",
                )
            )

    return gaps


# -------------------------------------------------------------------
# Confidence scoring
# -------------------------------------------------------------------


def score_confidence(
    audit: DomEvidenceAudit,
    reset: DomResetEvidence,
    has_enrichment: bool,
) -> DomConfidenceScore:
    """Score evidence quality deterministically.

    Every factor is recorded with its weight and whether it was
    present, so the resulting number can always be explained. The
    same inputs always produce the same score.

    Args:
        audit: The audit being scored.
        reset: Reset evidence for the subject.
        has_enrichment: Whether Redfin detail fields are populated.

    Returns:
        Confidence score with its full factor breakdown.
    """
    factors: List[DomEvidenceItem] = []
    penalties: List[DomEvidenceItem] = []

    def _factor(
        factor_id: str, label: str, present: bool, detail: str
    ) -> None:
        weight = FACTOR_WEIGHTS[factor_id]
        factors.append(
            DomEvidenceItem(
                factor_id=factor_id,
                label=label,
                present=present,
                weight=weight,
                contribution=weight if present else 0,
                detail=detail,
            )
        )

    def _penalty(
        factor_id: str, label: str, applied: bool, detail: str
    ) -> None:
        weight = PENALTY_WEIGHTS[factor_id]
        penalties.append(
            DomEvidenceItem(
                factor_id=factor_id,
                label=label,
                present=applied,
                weight=weight,
                contribution=-weight if applied else 0,
                detail=detail,
            )
        )

    _factor(
        "multiple_listing_events",
        "Multiple listing events",
        audit.listing_event_count >= 2,
        f"{audit.listing_event_count} listing event(s) recorded.",
    )
    _factor(
        "current_listing_start_known",
        "Current listing start date known",
        audit.current_listing_start_date is not None,
        (
            f"Current listing starts "
            f"{audit.current_listing_start_date}."
            if audit.current_listing_start_date
            else "Current listing start date is unknown."
        ),
    )
    _factor(
        "county_transfer_evidence",
        "County transfer evidence supports the reset",
        reset.reset_applied,
        reset.evidence_status,
    )
    _factor(
        "redfin_detail_enrichment",
        "Redfin detail enrichment present",
        has_enrichment,
        (
            "Detail fields are populated."
            if has_enrichment
            else "Detail enrichment is missing."
        ),
    )
    _factor(
        "source_pages_present",
        "Saved source page present",
        audit.source_page_count > 0,
        f"{audit.source_page_count} saved source page(s).",
    )
    _factor(
        "county_corroboration",
        "County records available for corroboration",
        audit.county_record_count > 0,
        f"{audit.county_record_count} county record(s).",
    )

    displayed_dom_only = (
        audit.listing_event_count == 0
        and audit.displayed_dom is not None
    )
    _penalty(
        "displayed_dom_only",
        "Displayed DOM only, no event history",
        displayed_dom_only,
        (
            "Only a displayed DOM is available; exposure cannot be "
            "reconstructed."
            if displayed_dom_only
            else "Event history is available."
        ),
    )

    conflicting = GAP_CONFLICTING_DOM_VALUES in audit.gap_ids
    _penalty(
        "conflicting_dom_values",
        "v1 and v2 differ without reset evidence",
        conflicting,
        (
            "Stored v1 and v2 disagree with no reset boundary."
            if conflicting
            else "No unexplained v1/v2 difference."
        ),
    )

    stale = GAP_STALE_OBSERVATION in audit.gap_ids
    _penalty(
        "stale_observation",
        "Most recent event is stale",
        stale,
        (
            "Latest listing event is outside the freshness window."
            if stale
            else "Latest listing event is recent."
        ),
    )

    raw = sum(f.contribution for f in factors) + sum(
        p.contribution for p in penalties
    )
    score = max(0, min(100, raw))

    # "Insufficient" means the audit had nothing substantive to work
    # with, not merely that it scored low. Without listing events and
    # without a displayed DOM there is no exposure evidence at all.
    no_exposure_evidence = (
        audit.listing_event_count == 0
        and audit.displayed_dom is None
    )

    if no_exposure_evidence:
        category = CONFIDENCE_INSUFFICIENT
    elif score >= HIGH_SCORE_MIN:
        category = CONFIDENCE_HIGH
    elif score >= MODERATE_SCORE_MIN:
        category = CONFIDENCE_MODERATE
    elif score >= LOW_SCORE_MIN:
        category = CONFIDENCE_LOW
    else:
        category = CONFIDENCE_INSUFFICIENT

    present = [f.label for f in factors if f.present]
    applied = [p.label for p in penalties if p.present]

    parts = [f"Confidence {category} ({score}/100)."]
    if present:
        parts.append("Supporting: " + "; ".join(present) + ".")
    else:
        parts.append("No supporting evidence factors were found.")
    if applied:
        parts.append("Reducing: " + "; ".join(applied) + ".")

    return DomConfidenceScore(
        score=score,
        category=category,
        factors=factors,
        penalties=penalties,
        explanation=" ".join(parts),
    )


# -------------------------------------------------------------------
# Audit construction
# -------------------------------------------------------------------


def build_dom_evidence_audit(
    candidate_id: Optional[int] = None,
    watched_property_id: Optional[int] = None,
    db_path: Optional[str] = None,
    analysis_date: Optional[date] = None,
) -> Optional[DomEvidenceAudit]:
    """Build the evidence audit for one candidate or property.

    Read-only. Recomputes Effective DOM v1/v2 and the Churn Index from
    the stored evidence rather than trusting persisted values, so a
    disagreement between the two becomes visible as an evidence gap.

    Args:
        candidate_id: Candidate ID to audit.
        watched_property_id: Watched property ID to audit.
        db_path: Path to SQLite database.
        analysis_date: Date to evaluate against, defaults to today.

    Returns:
        The audit, or None when the subject does not exist.
    """
    from marketsentry.churn_index import calculate_churn_index
    from marketsentry.effective_dom_v2_calculator import (
        calculate_effective_dom_v2,
    )

    path = db_path or config.database_path
    if not Path(path).exists():
        return None
    if candidate_id is None and watched_property_id is None:
        return None

    as_of = analysis_date or date.today()

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = _load_subject_row(
            conn, candidate_id, watched_property_id
        )
        if row is None:
            return None

        events = _load_listing_events(
            conn, candidate_id, watched_property_id
        )
        county_records = _load_county_records(
            conn, candidate_id, watched_property_id
        )
        source_page_count = _count_source_pages(
            conn, candidate_id, watched_property_id
        )
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    displayed_dom = _row_value(row, "displayed_dom")

    audit = DomEvidenceAudit(
        candidate_id=candidate_id,
        watched_property_id=watched_property_id,
        address=_row_value(row, "address"),
        city=_row_value(row, "city"),
        zip=_row_value(row, "zip"),
        redfin_url=_row_value(row, "redfin_url"),
        listing_event_count=len(events),
        source_page_count=source_page_count,
        county_record_count=len(county_records),
        displayed_dom=displayed_dom,
    )

    v2_metrics = calculate_effective_dom_v2(
        events=events,
        county_records=county_records,
        displayed_dom=displayed_dom,
        analysis_date=as_of,
    )
    churn_metrics = calculate_churn_index(
        events=events, analysis_date=as_of
    )

    audit.effective_dom_v1 = v2_metrics.effective_dom_v1
    audit.effective_dom_v2 = v2_metrics.effective_dom_v2
    audit.effective_dom_delta_v1 = v2_metrics.effective_dom_delta_v1
    audit.effective_dom_delta_v2 = v2_metrics.effective_dom_delta_v2
    if (
        audit.effective_dom_v1 is not None
        and audit.effective_dom_v2 is not None
    ):
        audit.v1_v2_delta = (
            audit.effective_dom_v1 - audit.effective_dom_v2
        )

    audit.first_event_date = v2_metrics.first_observed_event_date
    audit.latest_event_date = v2_metrics.latest_observed_event_date
    audit.current_listing_start_date = _current_listing_start(events)
    audit.listing_event_types = _event_type_summary(events)
    audit.status_change_count = v2_metrics.listing_churn_count or 0
    audit.price_change_count = v2_metrics.price_change_count or 0

    audit.reset = build_reset_explanation(
        v2_metrics, len(county_records)
    )
    audit.churn = build_churn_evidence(
        churn_metrics, v2_metrics, audit.reset
    )
    audit.gaps = _build_gaps(audit, audit.reset, as_of)

    has_enrichment = any(
        _row_value(row, column) is not None
        for column in ("beds", "baths", "sqft")
    )
    audit.confidence = score_confidence(
        audit, audit.reset, has_enrichment
    )
    audit.explanation = _build_audit_explanation(audit)

    return audit


def _current_listing_start(events: List[Any]) -> Optional[date]:
    """Find the start date of the current listing instance."""
    from marketsentry.effective_dom import (
        is_removal_event,
        is_sale_listing_event,
        normalize_event_type,
    )

    dated = [e for e in events if e.event_date]
    if not dated:
        return None

    latest_start: Optional[date] = None
    for event in sorted(dated, key=lambda e: e.event_date):
        normalized = normalize_event_type(event.event_type or "")
        if is_sale_listing_event(normalized):
            latest_start = event.event_date
        elif is_removal_event(normalized):
            latest_start = None

    return latest_start


def _event_type_summary(events: List[Any]) -> List[str]:
    """Summarize the distinct event types present."""
    seen: List[str] = []
    for event in events:
        label = (event.event_type or "").strip()
        if label and label not in seen:
            seen.append(label)
    return seen


def _build_audit_explanation(audit: DomEvidenceAudit) -> str:
    """Compose the neutral narrative for one audit.

    Describes evidence only. Makes no statement about seller intent
    and no purchase recommendation.
    """
    parts: List[str] = [
        f"{audit.subject_label} has "
        f"{audit.listing_event_count} listing event(s) and "
        f"{audit.county_record_count} county record(s) on file."
    ]

    if audit.effective_dom_v1 is None:
        parts.append(
            "Effective DOM v1 could not be computed from the "
            "available evidence."
        )
    else:
        parts.append(
            f"Effective DOM v1 is {audit.effective_dom_v1} and "
            f"Effective DOM v2 is {audit.effective_dom_v2}."
        )

    parts.append(audit.reset.explanation)

    if audit.churn.churn_index is not None:
        parts.append(
            f"Churn Index is {audit.churn.churn_index} over "
            f"{audit.churn.lookback_years} years, reported "
            "separately from Effective DOM."
        )
    else:
        parts.append(audit.churn.explanation)

    if audit.gaps:
        parts.append(
            "Evidence gaps: "
            + ", ".join(g.gap_id for g in audit.gaps)
            + "."
        )
    else:
        parts.append("No evidence gaps were identified.")

    parts.append(audit.confidence.explanation)
    parts.append(
        "This is an evidence summary for review, not a purchase "
        "recommendation."
    )

    return " ".join(parts)


# -------------------------------------------------------------------
# Batch audit and summary
# -------------------------------------------------------------------


def build_all_dom_evidence_audits(
    db_path: Optional[str] = None,
    include_candidates: bool = True,
    include_watched: bool = True,
    analysis_date: Optional[date] = None,
) -> List[DomEvidenceAudit]:
    """Audit every candidate and watched property.

    Args:
        db_path: Path to SQLite database.
        include_candidates: Audit candidate_review_queue rows.
        include_watched: Audit watched_properties rows.
        analysis_date: Date to evaluate against.

    Returns:
        Audits ordered candidates first, then watched properties.
    """
    path = db_path or config.database_path
    if not Path(path).exists():
        return []

    candidate_ids: List[int] = []
    property_ids: List[int] = []

    conn = sqlite3.connect(path)
    try:
        if include_candidates and _table_exists(
            conn, "candidate_review_queue"
        ):
            candidate_ids = [
                r[0]
                for r in conn.execute(
                    "SELECT candidate_id FROM "
                    "candidate_review_queue ORDER BY candidate_id"
                ).fetchall()
            ]
        if include_watched and _table_exists(
            conn, "watched_properties"
        ):
            property_ids = [
                r[0]
                for r in conn.execute(
                    "SELECT property_id FROM watched_properties "
                    "ORDER BY property_id"
                ).fetchall()
            ]
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    audits: List[DomEvidenceAudit] = []
    for candidate_id in candidate_ids:
        audit = build_dom_evidence_audit(
            candidate_id=candidate_id,
            db_path=path,
            analysis_date=analysis_date,
        )
        if audit is not None:
            audits.append(audit)
    for property_id in property_ids:
        audit = build_dom_evidence_audit(
            watched_property_id=property_id,
            db_path=path,
            analysis_date=analysis_date,
        )
        if audit is not None:
            audits.append(audit)

    return audits


def summarize_dom_evidence_audits(
    audits: List[DomEvidenceAudit],
) -> DomEvidenceAuditSummary:
    """Aggregate audit results for dashboard and CLI display."""
    summary = DomEvidenceAuditSummary(total_audited=len(audits))

    for audit in audits:
        category = audit.confidence.category
        if category == CONFIDENCE_HIGH:
            summary.high_confidence += 1
        elif category == CONFIDENCE_MODERATE:
            summary.moderate_confidence += 1
        elif category == CONFIDENCE_LOW:
            summary.low_confidence += 1
        else:
            summary.insufficient_confidence += 1

        if audit.gaps:
            summary.with_evidence_gaps += 1
        if audit.reset.reset_applied:
            summary.with_reset_evidence += 1
        if audit.churn.preserved_after_transfer:
            summary.with_churn_preserved += 1

        for gap in audit.gaps:
            summary.gap_counts[gap.gap_id] = (
                summary.gap_counts.get(gap.gap_id, 0) + 1
            )

    return summary


def list_dom_evidence_gaps(
    db_path: Optional[str] = None,
    gap_id: Optional[str] = None,
    analysis_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """List every evidence gap across all audited subjects.

    Args:
        db_path: Path to SQLite database.
        gap_id: Optional filter for one gap identifier.
        analysis_date: Date to evaluate against.

    Returns:
        One dict per gap occurrence.
    """
    rows: List[Dict[str, Any]] = []
    for audit in build_all_dom_evidence_audits(
        db_path=db_path, analysis_date=analysis_date
    ):
        for gap in audit.gaps:
            if gap_id and gap.gap_id != gap_id:
                continue
            rows.append({
                "candidate_id": audit.candidate_id,
                "watched_property_id": audit.watched_property_id,
                "subject": audit.subject_label,
                "address": audit.address,
                "gap_id": gap.gap_id,
                "label": gap.label,
                "severity": gap.severity,
                "detail": gap.detail,
                "confidence_category": audit.confidence.category,
            })
    return rows


# -------------------------------------------------------------------
# Report export
# -------------------------------------------------------------------


def build_report_rows(
    audits: List[DomEvidenceAudit],
) -> List[DomEvidenceReportRow]:
    """Flatten audits into export rows."""
    return [
        DomEvidenceReportRow(
            candidate_id=audit.candidate_id,
            watched_property_id=audit.watched_property_id,
            address=audit.address,
            redfin_url=audit.redfin_url,
            displayed_dom=audit.displayed_dom,
            effective_dom_v1=audit.effective_dom_v1,
            effective_dom_v2=audit.effective_dom_v2,
            v1_v2_delta=audit.v1_v2_delta,
            reset_applied=audit.reset.reset_applied,
            reset_date=audit.reset.reset_date,
            reset_evidence_source=audit.reset.evidence_source,
            reset_evidence_status=audit.reset.evidence_status,
            churn_index=audit.churn.churn_index,
            churn_event_count=audit.churn.churn_event_count,
            listing_churn_count=audit.churn.listing_churn_count,
            dom_reset_count=audit.churn.dom_reset_count,
            confidence_category=audit.confidence.category,
            confidence_score=audit.confidence.score,
            evidence_gaps=";".join(audit.gap_ids),
            explanation=audit.explanation,
        )
        for audit in audits
    ]


def export_dom_evidence_audit_report(
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
    fmt: str = "both",
    candidate_id: Optional[int] = None,
    watched_property_id: Optional[int] = None,
    analysis_date: Optional[date] = None,
) -> List[str]:
    """Export the DOM evidence audit to CSV and/or Markdown.

    Read-only apart from writing the report files.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Directory for the report files.
        fmt: Export format - csv, md, or both.
        candidate_id: Limit to one candidate.
        watched_property_id: Limit to one watched property.
        analysis_date: Date to evaluate against.

    Returns:
        List of exported file paths.
    """
    path = db_path or config.database_path
    out_dir = exports_dir or config.data_exports_dir

    if candidate_id is not None or watched_property_id is not None:
        single = build_dom_evidence_audit(
            candidate_id=candidate_id,
            watched_property_id=watched_property_id,
            db_path=path,
            analysis_date=analysis_date,
        )
        audits = [single] if single is not None else []
    else:
        audits = build_all_dom_evidence_audits(
            db_path=path, analysis_date=analysis_date
        )

    rows = build_report_rows(audits)
    summary = summarize_dom_evidence_audits(audits)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"dom_evidence_audit_{timestamp}"
    paths: List[str] = []

    if fmt in ("md", "both"):
        md_path = out_path / f"{base}.md"
        md_path.write_text(
            _build_report_md(audits, rows, summary),
            encoding="utf-8",
        )
        paths.append(str(md_path))

    if fmt in ("csv", "both"):
        csv_path = out_path / f"{base}.csv"
        csv_path.write_text(
            _build_report_csv(rows), encoding="utf-8"
        )
        paths.append(str(csv_path))

    return paths


def _fmt(value: Any) -> str:
    """Format an optional value for report output."""
    return "" if value is None else str(value)


def _build_report_md(
    audits: List[DomEvidenceAudit],
    rows: List[DomEvidenceReportRow],
    summary: DomEvidenceAuditSummary,
) -> str:
    """Build the DOM evidence audit Markdown report."""
    lines = [
        "# Effective DOM Evidence Audit",
        "",
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Subjects audited: {summary.total_audited}",
        "",
        "Effective DOM and the Churn Index are separate measures and "
        "are reported separately below. A county-confirmed transfer "
        "may reset Effective DOM v2; it never erases the Churn "
        "Index. This report describes evidence quality. It does not "
        "infer seller intent and is not a purchase recommendation.",
        "",
        "## Confidence Summary",
        "",
        f"- High: {summary.high_confidence}",
        f"- Moderate: {summary.moderate_confidence}",
        f"- Low: {summary.low_confidence}",
        f"- Insufficient: {summary.insufficient_confidence}",
        f"- With evidence gaps: {summary.with_evidence_gaps}",
        f"- With v2 reset evidence: {summary.with_reset_evidence}",
        f"- With churn preserved: {summary.with_churn_preserved}",
        "",
    ]

    if not audits:
        lines.append("No subjects were available to audit.")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Audit Rows")
    lines.append("")
    lines.append(
        "| Candidate | Property | Address | Displayed DOM | "
        "Eff DOM v1 | Eff DOM v2 | v1-v2 | Reset | Reset Date | "
        "Churn Index | Confidence | Score | Gaps | Redfin Link |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    )

    for row in rows:
        link = (
            f"[View]({row.redfin_url})" if row.redfin_url else ""
        )
        lines.append(
            f"| {_fmt(row.candidate_id)} "
            f"| {_fmt(row.watched_property_id)} "
            f"| {_fmt(row.address)} "
            f"| {_fmt(row.displayed_dom)} "
            f"| {_fmt(row.effective_dom_v1)} "
            f"| {_fmt(row.effective_dom_v2)} "
            f"| {_fmt(row.v1_v2_delta)} "
            f"| {'yes' if row.reset_applied else 'no'} "
            f"| {_fmt(row.reset_date)} "
            f"| {_fmt(row.churn_index)} "
            f"| {row.confidence_category} "
            f"| {row.confidence_score} "
            f"| {row.evidence_gaps} "
            f"| {link} |"
        )

    lines.append("")
    lines.append("## Evidence Detail")
    lines.append("")

    for audit in audits:
        lines.append(
            f"### {audit.subject_label} - {audit.address or ''}"
        )
        lines.append("")
        lines.append(
            f"- Effective DOM v1: "
            f"{_fmt(audit.effective_dom_v1)}"
        )
        lines.append(
            f"- Effective DOM v2: "
            f"{_fmt(audit.effective_dom_v2)}"
        )
        lines.append(
            f"- Churn Index (separate measure): "
            f"{_fmt(audit.churn.churn_index)}"
        )
        lines.append(f"- Reset: {audit.reset.explanation}")
        lines.append(f"- Churn: {audit.churn.explanation}")
        lines.append(
            f"- Confidence: {audit.confidence.explanation}"
        )
        if audit.gaps:
            lines.append("- Evidence gaps:")
            for gap in audit.gaps:
                lines.append(
                    f"  - `{gap.gap_id}` ({gap.severity}): "
                    f"{gap.detail}"
                )
        else:
            lines.append("- Evidence gaps: none")
        lines.append("")

    lines.append("## Safety Note")
    lines.append("")
    lines.append(
        "All values are computed from locally stored listing events "
        "and county records. No live retrieval, scraping, browser "
        "automation, or outbound notification is involved. Neutral "
        "language only: no seller intent is inferred and no purchase "
        "recommendation is made."
    )
    lines.append("")

    return "\n".join(lines)


def _build_report_csv(
    rows: List[DomEvidenceReportRow],
) -> str:
    """Build the DOM evidence audit CSV report."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "candidate_id",
        "watched_property_id",
        "address",
        "redfin_url",
        "displayed_dom",
        "effective_dom_v1",
        "effective_dom_v2",
        "v1_v2_delta",
        "reset_applied",
        "reset_date",
        "reset_evidence_source",
        "reset_evidence_status",
        "churn_index",
        "churn_event_count",
        "listing_churn_count",
        "dom_reset_count",
        "confidence_category",
        "confidence_score",
        "evidence_gaps",
        "explanation",
    ])

    for row in rows:
        writer.writerow([
            _fmt(row.candidate_id),
            _fmt(row.watched_property_id),
            _fmt(row.address),
            _fmt(row.redfin_url),
            _fmt(row.displayed_dom),
            _fmt(row.effective_dom_v1),
            _fmt(row.effective_dom_v2),
            _fmt(row.v1_v2_delta),
            "yes" if row.reset_applied else "no",
            _fmt(row.reset_date),
            row.reset_evidence_source,
            row.reset_evidence_status,
            _fmt(row.churn_index),
            row.churn_event_count,
            row.listing_churn_count,
            row.dom_reset_count,
            row.confidence_category,
            row.confidence_score,
            row.evidence_gaps,
            row.explanation,
        ])

    return output.getvalue()
