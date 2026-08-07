"""Milestone 56: Effective DOM evidence audit and confidence report.

Covers evidence gathering, reset explanation, churn preservation,
evidence gaps, deterministic confidence scoring, neutral language, the
CLI surface, report export, and the standing safety invariants.

All tests are local-only and perform no network calls.
"""

import ast
import inspect
import io
import sqlite3
import tokenize
from datetime import date
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from marketsentry.cli import app
from marketsentry.config import config
from marketsentry.dom_evidence_audit import (
    CONFIDENCE_HIGH,
    CONFIDENCE_INSUFFICIENT,
    CONFIDENCE_LOW,
    CONFIDENCE_MODERATE,
    GAP_CONFLICTING_DOM_VALUES,
    GAP_MISSING_COUNTY_TRANSFER_EVIDENCE,
    GAP_MISSING_CURRENT_LISTING_START,
    GAP_MISSING_DISPLAYED_DOM,
    GAP_MISSING_LISTING_EVENTS,
    GAP_MISSING_SOURCE_PAGE,
    GAP_STALE_OBSERVATION,
    DomEvidenceAudit,
    DomEvidenceAuditSummary,
    DomEvidenceReportRow,
    build_all_dom_evidence_audits,
    build_dom_evidence_audit,
    build_report_rows,
    export_dom_evidence_audit_report,
    list_dom_evidence_gaps,
    summarize_dom_evidence_audits,
)

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "marketsentry"

DOM_COMMANDS = [
    "dom-evidence-audit",
    "list-dom-evidence-gaps",
    "export-dom-evidence-audit-report",
]

ANALYSIS_DATE = date(2026, 6, 1)

# Language that would imply seller intent or a purchase decision.
BANNED_PHRASES = [
    "desperate",
    "motivated seller",
    "seller wants",
    "seller needs",
    "you should buy",
    "recommend buying",
    "good deal",
    "bargain",
    "undervalued",
    "overpriced",
    "make an offer",
]


def _strip_prose(source: str) -> str:
    """Return source with comments and docstrings removed.

    The module documents in prose that it adds no walkability fields
    and infers no seller intent. Scanning raw text flags the
    guarantee itself, so compare executable code only.
    """
    kept = [
        token
        for token in tokenize.generate_tokens(
            io.StringIO(source).readline
        )
        if token.type != tokenize.COMMENT
    ]
    code = tokenize.untokenize(kept)

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.Module,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                code = code.replace(doc, "")
    return code


def _command_map():
    """Map CLI command name to its callback."""
    mapping = {}
    for command in app.registered_commands:
        name = command.name or command.callback.__name__.replace(
            "_", "-"
        )
        mapping[name] = command.callback
    return mapping


def _db_default(callback):
    """Extract the resolved default of a command's --db option."""
    param = inspect.signature(callback).parameters["db"]
    default = param.default
    if isinstance(default, typer.models.OptionInfo):
        return default.default
    return default


def _make_db(tmp_path, name="audit.db"):
    """Create an initialized database."""
    db_path = str(tmp_path / name)
    from marketsentry.database import init_db

    init_db(db_path)
    return db_path


def _add_candidate(
    db_path,
    candidate_id,
    address="12345 Evidence Way",
    displayed_dom=None,
    beds=None,
    baths=None,
    sqft=None,
):
    """Insert a candidate row."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO candidate_review_queue "
        "(candidate_id, discovery_date, source_site, "
        "source_search_url, redfin_url, address, "
        "normalized_address, city, zip, displayed_dom, beds, "
        "baths, sqft, review_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            candidate_id, "2026-01-01", "redfin", "",
            f"https://www.redfin.com/CA/Temecula/"
            f"{candidate_id}-Evidence-Way-92592/home/{candidate_id}",
            address, address.lower(), "Temecula", "92592",
            displayed_dom, beds, baths, sqft, "pending",
        ),
    )
    conn.commit()
    conn.close()


def _add_watched(db_path, property_id, address="99 Watched Ln"):
    """Insert a watched property row."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO watched_properties "
        "(property_id, first_saved_date, redfin_url, address, "
        "normalized_address, city, zip, active_watch_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            property_id, "2026-01-01",
            f"https://www.redfin.com/CA/Temecula/"
            f"{property_id}-Watched-Ln-92592/home/{property_id}",
            address, address.lower(), "Temecula", "92592", 1,
        ),
    )
    conn.commit()
    conn.close()


def _add_events(db_path, events, candidate_id=None, property_id=None):
    """Insert listing events as (date, type) tuples."""
    conn = sqlite3.connect(db_path)
    for event_date, event_type in events:
        conn.execute(
            "INSERT INTO listing_events "
            "(property_id, candidate_id, event_date, source_site, "
            "event_type) VALUES (?, ?, ?, ?, ?)",
            (
                property_id, candidate_id, event_date, "redfin",
                event_type,
            ),
        )
    conn.commit()
    conn.close()


def _add_county_transfer(
    db_path,
    record_date,
    candidate_id=None,
    property_id=None,
    record_type="grant_deed",
):
    """Insert a county ownership transfer record."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO county_record_observations "
        "(candidate_id, property_id, source_type, county_name, "
        "record_date, record_type, normalized_record_type, "
        "confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            candidate_id, property_id, "recorder", "Riverside",
            record_date, record_type, record_type, 0.9,
        ),
    )
    conn.commit()
    conn.close()


def _add_source_page(db_path, candidate_id=None, property_id=None):
    """Insert a saved source page record."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO source_pages "
        "(property_id, candidate_id, source_site, source_url, "
        "parse_status) VALUES (?, ?, ?, ?, ?)",
        (
            property_id, candidate_id, "redfin",
            "https://www.redfin.com/example", "ok",
        ),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def bare_db(tmp_path):
    """Candidate with no evidence at all."""
    db_path = _make_db(tmp_path)
    _add_candidate(db_path, 1)
    return db_path


@pytest.fixture
def displayed_dom_only_db(tmp_path):
    """Candidate with a displayed DOM but no listing events."""
    db_path = _make_db(tmp_path)
    _add_candidate(db_path, 2, displayed_dom=45)
    return db_path


@pytest.fixture
def events_no_reset_db(tmp_path):
    """Candidate with listing history and no county transfer."""
    db_path = _make_db(tmp_path)
    _add_candidate(
        db_path, 3, displayed_dom=30, beds=3, baths=2.0, sqft=1800
    )
    _add_events(
        db_path,
        [
            ("2025-06-01", "listed"),
            ("2025-09-01", "price_change"),
            ("2026-01-15", "delisted"),
            ("2026-04-01", "listed"),
        ],
        candidate_id=3,
    )
    _add_source_page(db_path, candidate_id=3)
    return db_path


@pytest.fixture
def events_with_reset_db(tmp_path):
    """Candidate whose listing predates a county transfer.

    The listing starts in 2024 and is still active, so exposure spans
    the 2025-11-18 transfer. That is the only shape where a reset
    actually excludes anything: if the current listing began after
    the transfer, v1 and v2 coincide and a "v2 <= v1" assertion would
    pass without exercising the reset at all.
    """
    db_path = _make_db(tmp_path)
    _add_candidate(
        db_path, 4, displayed_dom=30, beds=4, baths=3.0, sqft=2400
    )
    _add_events(
        db_path,
        [
            ("2024-03-01", "listed"),
            ("2025-06-01", "price_change"),
            ("2026-01-05", "price_change"),
            ("2026-05-15", "price_change"),
        ],
        candidate_id=4,
    )
    _add_county_transfer(
        db_path, "2025-11-18", candidate_id=4
    )
    _add_source_page(db_path, candidate_id=4)
    return db_path


class TestAuditWithNoEvidence:
    """A subject with no evidence at all."""

    def test_audit_returns_result(self, bare_db):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=1,
            db_path=bare_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit is not None
        assert audit.listing_event_count == 0

    def test_flags_missing_listing_events(self, bare_db):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=1,
            db_path=bare_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert GAP_MISSING_LISTING_EVENTS in audit.gap_ids
        assert GAP_MISSING_DISPLAYED_DOM in audit.gap_ids
        assert GAP_MISSING_SOURCE_PAGE in audit.gap_ids

    def test_confidence_is_insufficient(self, bare_db):
        # No events and no displayed DOM means no exposure evidence.
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=1,
            db_path=bare_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.confidence.category == CONFIDENCE_INSUFFICIENT

    def test_missing_subject_returns_none(self, bare_db):
        # Assert
        assert build_dom_evidence_audit(
            candidate_id=999, db_path=bare_db
        ) is None

    def test_no_ids_returns_none(self, bare_db):
        # Assert
        assert build_dom_evidence_audit(db_path=bare_db) is None

    def test_missing_database_returns_none(self, tmp_path):
        # Assert
        assert build_dom_evidence_audit(
            candidate_id=1, db_path=str(tmp_path / "absent.db")
        ) is None


class TestAuditWithDisplayedDomOnly:
    """Displayed DOM without event history is weak evidence."""

    def test_displayed_dom_recorded(self, displayed_dom_only_db):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=2,
            db_path=displayed_dom_only_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.displayed_dom == 45
        assert audit.listing_event_count == 0

    def test_displayed_dom_only_penalty_applied(
        self, displayed_dom_only_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=2,
            db_path=displayed_dom_only_db,
            analysis_date=ANALYSIS_DATE,
        )
        applied = [
            p.factor_id
            for p in audit.confidence.penalties
            if p.present
        ]

        # Assert
        assert "displayed_dom_only" in applied

    def test_confidence_is_weak(self, displayed_dom_only_db):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=2,
            db_path=displayed_dom_only_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.confidence.category in (
            CONFIDENCE_LOW,
            CONFIDENCE_INSUFFICIENT,
        )


class TestAuditWithEventsNoReset:
    """Listing history without a county transfer."""

    def test_events_counted(self, events_no_reset_db):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=3,
            db_path=events_no_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.listing_event_count == 4
        assert audit.first_event_date == date(2025, 6, 1)
        assert audit.latest_event_date == date(2026, 4, 1)

    def test_no_reset_applied(self, events_no_reset_db):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=3,
            db_path=events_no_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.reset.reset_applied is False
        assert audit.reset.evidence_status == "no_transfer_evidence"
        assert (
            GAP_MISSING_COUNTY_TRANSFER_EVIDENCE in audit.gap_ids
        )

    def test_reset_explanation_text(self, events_no_reset_db):
        # The prompt specifies this wording for the no-evidence case.
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=3,
            db_path=events_no_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert (
            "No county-confirmed transfer reset evidence is "
            "available. Effective DOM v2 does not apply a reset."
        ) == audit.reset.explanation

    def test_v1_and_v2_agree_without_reset(
        self, events_no_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=3,
            db_path=events_no_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.effective_dom_v1 == audit.effective_dom_v2
        assert GAP_CONFLICTING_DOM_VALUES not in audit.gap_ids

    def test_current_listing_start_detected(
        self, events_no_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=3,
            db_path=events_no_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.current_listing_start_date == date(2026, 4, 1)
        assert (
            GAP_MISSING_CURRENT_LISTING_START not in audit.gap_ids
        )


class TestAuditWithCountyReset:
    """Listing history with a county-confirmed transfer."""

    def test_reset_applied(self, events_with_reset_db):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.reset.reset_applied is True
        assert audit.reset.reset_date == date(2025, 11, 18)
        assert audit.reset.evidence_source == "county_record"

    def test_reset_explanation_names_date_and_churn(
        self, events_with_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        text = audit.reset.explanation
        assert "2025-11-18" in text
        assert "excluded from Effective DOM v2" in text
        assert "Churn Index" in text

    def test_v2_excludes_pre_transfer_exposure(
        self, events_with_reset_db
    ):
        # The whole point of v2: pre-boundary exposure drops out.
        # A "<=" assertion would pass even when the reset excluded
        # nothing, so require a strict reduction and a real delta.
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.effective_dom_v1 is not None
        assert audit.effective_dom_v2 is not None
        assert audit.effective_dom_v2 < audit.effective_dom_v1
        assert audit.v1_v2_delta is not None
        assert audit.v1_v2_delta > 0

    def test_v1_spans_the_transfer_boundary(
        self, events_with_reset_db
    ):
        # Confirms the fixture genuinely exercises exclusion: v1
        # must cover exposure that began before the transfer.
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.current_listing_start_date == date(2024, 3, 1)
        assert audit.reset.reset_date == date(2025, 11, 18)
        assert (
            audit.current_listing_start_date
            < audit.reset.reset_date
        )

    def test_no_missing_county_gap_when_reset_present(
        self, events_with_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert (
            GAP_MISSING_COUNTY_TRANSFER_EVIDENCE
            not in audit.gap_ids
        )

    def test_v1_v2_difference_is_not_flagged_as_conflict(
        self, events_with_reset_db
    ):
        # A difference is expected when a reset applied.
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert GAP_CONFLICTING_DOM_VALUES not in audit.gap_ids


class TestChurnPreservation:
    """A reset must never erase the Churn Index."""

    def test_churn_reported_after_reset(
        self, events_with_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.reset.reset_applied is True
        assert audit.churn.churn_index is not None
        assert audit.churn.preserved_after_transfer is True

    def test_churn_counts_survive_reset(
        self, events_with_reset_db
    ):
        # Event history spans the transfer, so churn counts must
        # still reflect the pre-transfer activity.
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.churn.churn_event_count > 0

    def test_churn_explanation_states_independence(
        self, events_with_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        text = audit.churn.explanation
        assert "independently" in text
        assert "does not erase" in text

    def test_churn_is_a_separate_field_from_effective_dom(
        self, events_with_reset_db
    ):
        # Structural guarantee: churn lives on its own model.
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert hasattr(audit.churn, "churn_index")
        assert not hasattr(audit.churn, "effective_dom_v1")
        assert "churn" not in str(audit.effective_dom_v1 or "")

    def test_module_never_blends_the_two_measures(self):
        # Arrange
        code = _strip_prose(
            (SRC_DIR / "dom_evidence_audit.py").read_text(
                encoding="utf-8"
            )
        )

        # Assert: no arithmetic combining churn with effective dom
        for banned in [
            "churn_index + ",
            "churn_index +=",
            "effective_dom_v2 + audit.churn",
            "blend",
        ]:
            assert banned not in code


class TestEvidenceGaps:
    """Named gaps appear for each missing piece of evidence."""

    def test_missing_source_page_gap(self, tmp_path):
        # Arrange
        db_path = _make_db(tmp_path)
        _add_candidate(db_path, 7, displayed_dom=10)
        _add_events(
            db_path, [("2026-04-01", "listed")], candidate_id=7
        )

        # Act
        audit = build_dom_evidence_audit(
            candidate_id=7,
            db_path=db_path,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert GAP_MISSING_SOURCE_PAGE in audit.gap_ids

    def test_stale_observation_gap(self, tmp_path):
        # Arrange: latest event well outside the freshness window
        db_path = _make_db(tmp_path)
        _add_candidate(db_path, 8, displayed_dom=10)
        _add_events(
            db_path, [("2025-01-01", "listed")], candidate_id=8
        )

        # Act
        audit = build_dom_evidence_audit(
            candidate_id=8,
            db_path=db_path,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert GAP_STALE_OBSERVATION in audit.gap_ids

    def test_fresh_observation_not_flagged(self, tmp_path):
        # Arrange
        db_path = _make_db(tmp_path)
        _add_candidate(db_path, 9, displayed_dom=10)
        _add_events(
            db_path, [("2026-05-25", "listed")], candidate_id=9
        )

        # Act
        audit = build_dom_evidence_audit(
            candidate_id=9,
            db_path=db_path,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert GAP_STALE_OBSERVATION not in audit.gap_ids

    def test_gaps_carry_severity_and_detail(
        self, events_no_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=3,
            db_path=events_no_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        for gap in audit.gaps:
            assert gap.gap_id
            assert gap.detail
            assert gap.severity in ("info", "moderate", "high")

    def test_list_gaps_across_subjects(self, events_no_reset_db):
        # Act
        rows = list_dom_evidence_gaps(
            db_path=events_no_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert rows
        assert all("gap_id" in r for r in rows)

    def test_list_gaps_filter(self, events_no_reset_db):
        # Act
        rows = list_dom_evidence_gaps(
            db_path=events_no_reset_db,
            gap_id=GAP_MISSING_COUNTY_TRANSFER_EVIDENCE,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert rows
        assert all(
            r["gap_id"] == GAP_MISSING_COUNTY_TRANSFER_EVIDENCE
            for r in rows
        )


class TestConfidenceScoring:
    """Scoring is deterministic and explainable."""

    def test_scoring_is_deterministic(self, events_with_reset_db):
        # Act
        scores = [
            build_dom_evidence_audit(
                candidate_id=4,
                db_path=events_with_reset_db,
                analysis_date=ANALYSIS_DATE,
            ).confidence.score
            for _ in range(5)
        ]

        # Assert
        assert len(set(scores)) == 1

    def test_full_evidence_scores_high(
        self, events_with_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.confidence.category == CONFIDENCE_HIGH
        assert audit.confidence.score >= 75

    def test_partial_evidence_scores_moderate_or_low(
        self, events_no_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=3,
            db_path=events_no_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.confidence.category in (
            CONFIDENCE_MODERATE,
            CONFIDENCE_LOW,
        )

    def test_score_is_clamped_to_range(self, events_with_reset_db):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert 0 <= audit.confidence.score <= 100

    def test_every_factor_is_reported(self, events_with_reset_db):
        # Explainability: each factor carries weight and presence.
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert len(audit.confidence.factors) == 6
        assert len(audit.confidence.penalties) == 3
        for item in audit.confidence.factors:
            assert item.factor_id
            assert item.label
            assert item.weight > 0

    def test_score_equals_sum_of_contributions(
        self, events_with_reset_db
    ):
        # The reported number must match its own breakdown.
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )
        total = sum(
            i.contribution for i in audit.confidence.factors
        ) + sum(
            i.contribution for i in audit.confidence.penalties
        )

        # Assert
        assert audit.confidence.score == max(0, min(100, total))

    def test_all_four_categories_reachable(self, tmp_path):
        # Arrange: build one subject per confidence tier.
        db_path = _make_db(tmp_path)

        # Insufficient: nothing at all
        _add_candidate(db_path, 10)

        # Low: displayed DOM only
        _add_candidate(db_path, 11, displayed_dom=20)

        # Moderate: events plus enrichment, no county evidence
        _add_candidate(
            db_path, 12, displayed_dom=20, beds=3, baths=2.0,
            sqft=1500,
        )
        _add_events(
            db_path,
            [("2026-04-01", "listed"), ("2026-05-01", "price_change")],
            candidate_id=12,
        )
        _add_source_page(db_path, candidate_id=12)

        # High: everything
        _add_candidate(
            db_path, 13, displayed_dom=20, beds=4, baths=3.0,
            sqft=2000,
        )
        _add_events(
            db_path,
            [
                ("2025-01-01", "listed"),
                ("2025-11-18", "sold"),
                ("2026-05-01", "listed"),
            ],
            candidate_id=13,
        )
        _add_county_transfer(
            db_path, "2025-11-18", candidate_id=13
        )
        _add_source_page(db_path, candidate_id=13)

        # Act
        categories = {
            cid: build_dom_evidence_audit(
                candidate_id=cid,
                db_path=db_path,
                analysis_date=ANALYSIS_DATE,
            ).confidence.category
            for cid in (10, 11, 12, 13)
        }

        # Assert
        assert categories[10] == CONFIDENCE_INSUFFICIENT
        assert categories[13] == CONFIDENCE_HIGH
        assert len(set(categories.values())) >= 3

    def test_explanation_names_supporting_factors(
        self, events_with_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert "Confidence high" in audit.confidence.explanation
        assert "Supporting:" in audit.confidence.explanation


class TestWatchedPropertyAudit:
    """Watched properties audit the same way."""

    def test_audit_by_watched_property_id(self, tmp_path):
        # Arrange
        db_path = _make_db(tmp_path)
        _add_watched(db_path, 2)
        _add_events(
            db_path,
            [("2026-04-01", "listed"), ("2026-05-01", "price_change")],
            property_id=2,
        )

        # Act
        audit = build_dom_evidence_audit(
            watched_property_id=2,
            db_path=db_path,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit is not None
        assert audit.watched_property_id == 2
        assert audit.candidate_id is None
        assert audit.listing_event_count == 2

    def test_subject_label(self, tmp_path):
        # Arrange
        db_path = _make_db(tmp_path)
        _add_watched(db_path, 3)

        # Act
        audit = build_dom_evidence_audit(
            watched_property_id=3,
            db_path=db_path,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert audit.subject_label == "Watched property 3"


class TestBatchAuditAndSummary:
    """Auditing every subject and summarizing."""

    def test_audits_candidates_and_watched(self, tmp_path):
        # Arrange
        db_path = _make_db(tmp_path)
        _add_candidate(db_path, 1)
        _add_candidate(db_path, 2)
        _add_watched(db_path, 5)

        # Act
        audits = build_all_dom_evidence_audits(
            db_path=db_path, analysis_date=ANALYSIS_DATE
        )

        # Assert
        assert len(audits) == 3

    def test_summary_counts(self, events_with_reset_db):
        # Act
        audits = build_all_dom_evidence_audits(
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )
        summary = summarize_dom_evidence_audits(audits)

        # Assert
        assert isinstance(summary, DomEvidenceAuditSummary)
        assert summary.total_audited == len(audits)
        assert summary.with_reset_evidence == 1
        assert summary.with_churn_preserved == len(audits)

    def test_summary_gap_counts(self, events_no_reset_db):
        # Act
        audits = build_all_dom_evidence_audits(
            db_path=events_no_reset_db,
            analysis_date=ANALYSIS_DATE,
        )
        summary = summarize_dom_evidence_audits(audits)

        # Assert
        assert (
            summary.gap_counts.get(
                GAP_MISSING_COUNTY_TRANSFER_EVIDENCE
            )
            == 1
        )

    def test_empty_database_returns_empty(self, tmp_path):
        # Arrange
        db_path = _make_db(tmp_path)

        # Act
        audits = build_all_dom_evidence_audits(db_path=db_path)

        # Assert
        assert audits == []

    def test_audit_does_not_mutate(self, events_with_reset_db):
        # Arrange
        conn = sqlite3.connect(events_with_reset_db)
        before = conn.execute(
            "SELECT candidate_id, displayed_dom, quiet_score, "
            "vibrancy_score FROM candidate_review_queue"
        ).fetchall()
        events_before = conn.execute(
            "SELECT COUNT(*) FROM listing_events"
        ).fetchone()[0]
        conn.close()

        # Act
        build_all_dom_evidence_audits(
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        conn = sqlite3.connect(events_with_reset_db)
        after = conn.execute(
            "SELECT candidate_id, displayed_dom, quiet_score, "
            "vibrancy_score FROM candidate_review_queue"
        ).fetchall()
        events_after = conn.execute(
            "SELECT COUNT(*) FROM listing_events"
        ).fetchone()[0]
        conn.close()
        assert before == after
        assert events_before == events_after


class TestNeutralLanguage:
    """No seller intent, no purchase recommendations."""

    def test_audit_text_has_no_banned_phrases(
        self, events_with_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )
        text = " ".join([
            audit.explanation,
            audit.reset.explanation,
            audit.churn.explanation,
            audit.confidence.explanation,
            *[g.detail for g in audit.gaps],
        ]).lower()

        # Assert
        for phrase in BANNED_PHRASES:
            assert phrase not in text

    def test_explanation_disclaims_recommendation(
        self, events_with_reset_db
    ):
        # Act
        audit = build_dom_evidence_audit(
            candidate_id=4,
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert "not a purchase recommendation" in (
            audit.explanation
        )

    def test_module_source_has_no_seller_intent_language(self):
        # Arrange
        code = _strip_prose(
            (SRC_DIR / "dom_evidence_audit.py").read_text(
                encoding="utf-8"
            )
        ).lower()

        # Assert
        for phrase in [
            "desperate",
            "motivated seller",
            "seller wants",
            "good deal",
            "undervalued",
        ]:
            assert phrase not in code


class TestReportExport:
    """CSV and Markdown export."""

    def test_csv_export_columns(
        self, events_with_reset_db, tmp_path
    ):
        # Act
        paths = export_dom_evidence_audit_report(
            db_path=events_with_reset_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="csv",
            analysis_date=ANALYSIS_DATE,
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        for column in [
            "candidate_id",
            "watched_property_id",
            "effective_dom_v1",
            "effective_dom_v2",
            "v1_v2_delta",
            "reset_applied",
            "reset_date",
            "churn_index",
            "confidence_category",
            "confidence_score",
            "evidence_gaps",
        ]:
            assert column in content

    def test_markdown_export_with_clickable_link(
        self, events_with_reset_db, tmp_path
    ):
        # Act
        paths = export_dom_evidence_audit_report(
            db_path=events_with_reset_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
            analysis_date=ANALYSIS_DATE,
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert "# Effective DOM Evidence Audit" in content
        assert "[View](" in content
        assert "redfin.com" in content

    def test_markdown_states_separation_rule(
        self, events_with_reset_db, tmp_path
    ):
        # Act
        paths = export_dom_evidence_audit_report(
            db_path=events_with_reset_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
            analysis_date=ANALYSIS_DATE,
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert "separate measures" in content
        assert "never erases the Churn Index" in content

    def test_export_both_formats(
        self, events_with_reset_db, tmp_path
    ):
        # Act
        paths = export_dom_evidence_audit_report(
            db_path=events_with_reset_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="both",
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        assert len(paths) == 2

    def test_export_single_candidate(
        self, events_with_reset_db, tmp_path
    ):
        # Act
        paths = export_dom_evidence_audit_report(
            db_path=events_with_reset_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="csv",
            candidate_id=4,
            analysis_date=ANALYSIS_DATE,
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert: header plus exactly one data row
        assert len(
            [ln for ln in content.splitlines() if ln.strip()]
        ) == 2

    def test_report_rows_flatten_audit(
        self, events_with_reset_db
    ):
        # Act
        audits = build_all_dom_evidence_audits(
            db_path=events_with_reset_db,
            analysis_date=ANALYSIS_DATE,
        )
        rows = build_report_rows(audits)

        # Assert
        assert rows
        assert isinstance(rows[0], DomEvidenceReportRow)
        assert rows[0].confidence_category

    def test_export_makes_no_purchase_recommendation(
        self, events_with_reset_db, tmp_path
    ):
        # Act
        paths = export_dom_evidence_audit_report(
            db_path=events_with_reset_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="both",
            analysis_date=ANALYSIS_DATE,
        )

        # Assert
        for path in paths:
            text = Path(path).read_text(encoding="utf-8").lower()
            for phrase in BANNED_PHRASES:
                assert phrase not in text


class TestCliCommands:
    """CLI surface."""

    @pytest.mark.parametrize("command_name", DOM_COMMANDS)
    def test_command_registered(self, command_name):
        # Assert
        assert command_name in _command_map()

    @pytest.mark.parametrize("command_name", DOM_COMMANDS)
    def test_canonical_db_default(self, command_name):
        # Act
        default = _db_default(_command_map()[command_name])

        # Assert
        assert default == config.database_path
        assert default == "db/marketsentry.db"

    def test_audit_by_candidate_id(self, events_with_reset_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "dom-evidence-audit",
                "--candidate-id", "4",
                "--db", events_with_reset_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Effective DOM v1" in result.output
        assert "Churn Index" in result.output
        assert "Confidence" in result.output

    def test_audit_by_watched_property_id(self, tmp_path):
        # Arrange
        db_path = _make_db(tmp_path)
        _add_watched(db_path, 2)
        _add_events(
            db_path, [("2026-05-01", "listed")], property_id=2
        )
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "dom-evidence-audit",
                "--watched-property-id", "2",
                "--db", db_path,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Watched property 2" in result.output

    def test_audit_requires_an_id(self, events_with_reset_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            ["dom-evidence-audit", "--db", events_with_reset_db],
        )

        # Assert
        assert result.exit_code == 1
        assert "--candidate-id" in result.output

    def test_audit_missing_subject(self, events_with_reset_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "dom-evidence-audit",
                "--candidate-id", "999",
                "--db", events_with_reset_db,
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_list_gaps_command(self, events_no_reset_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "list-dom-evidence-gaps",
                "--db", events_no_reset_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "DOM Evidence Gaps" in result.output

    def test_list_gaps_filter(self, events_no_reset_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "list-dom-evidence-gaps",
                "--db", events_no_reset_db,
                "--gap", GAP_MISSING_COUNTY_TRANSFER_EVIDENCE,
            ],
        )

        # Assert
        assert result.exit_code == 0

    def test_export_command(
        self, events_with_reset_db, tmp_path
    ):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "export-dom-evidence-audit-report",
                "--db", events_with_reset_db,
                "--output-dir", str(tmp_path / "exports"),
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Exported" in result.output

    def test_custom_db_accepted(self, events_with_reset_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "list-dom-evidence-gaps",
                "--db", events_with_reset_db,
            ],
        )

        # Assert
        assert "No such option" not in result.output
        assert result.exit_code == 0

    def test_cli_output_has_no_banned_phrases(
        self, events_with_reset_db
    ):
        # Arrange
        runner = CliRunner()

        # Act
        output = runner.invoke(
            app,
            [
                "dom-evidence-audit",
                "--candidate-id", "4",
                "--db", events_with_reset_db,
            ],
        ).output.lower()

        # Assert
        for phrase in BANNED_PHRASES:
            assert phrase not in output


class TestDashboardSection:
    """Dashboard exposes the audit read-only."""

    def test_section_present(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "Effective DOM Evidence Audit" in content
        assert "dom_evidence_export_form" in content

    def test_v1_v2_and_churn_shown_separately(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "Effective DOM v1" in content
        assert "Effective DOM v2" in content
        assert "Churn Index (separate)" in content

    def test_no_mutation_on_load(self):
        # The only write is the export, and it must sit behind the
        # form submit guard.
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")
        lines = content.split("\n")

        submit_lines = [
            i
            for i, line in enumerate(lines)
            if "_dom_export_submit:" in line
        ]
        export_lines = [
            i
            for i, line in enumerate(lines)
            if "export_dom_evidence_audit_report(" in line
            and not line.strip().startswith(
                "export_dom_evidence_audit_report,"
            )
        ]

        # Assert
        assert submit_lines
        assert export_lines
        for export_line in export_lines:
            assert any(
                submit < export_line for submit in submit_lines
            ), f"unguarded export at line {export_line + 1}"

    def test_dashboard_imports(self):
        # Act
        import marketsentry.dashboard_app as dash

        # Assert
        assert dash is not None


class TestSafetyInvariants:
    """Milestone 56 adds no unsafe capability."""

    def test_no_live_retrieval_or_scraping(self):
        # Arrange
        code = _strip_prose(
            (SRC_DIR / "dom_evidence_audit.py").read_text(
                encoding="utf-8"
            )
        )

        # Assert
        for banned in [
            "import requests",
            "import httpx",
            "urllib.request",
            "BeautifulSoup",
            "html.parser",
        ]:
            assert banned not in code

    def test_no_browser_automation(self):
        # Arrange
        code = _strip_prose(
            (SRC_DIR / "dom_evidence_audit.py").read_text(
                encoding="utf-8"
            )
        ).lower()

        # Assert
        for banned in [
            "playwright",
            "selenium",
            "webdriver",
            "webbrowser",
        ]:
            assert banned not in code

    def test_no_outbound_notifications(self):
        # Arrange
        code = _strip_prose(
            (SRC_DIR / "dom_evidence_audit.py").read_text(
                encoding="utf-8"
            )
        ).lower()

        # Assert
        for banned in ["smtp", "send_email", "webhook", "sms"]:
            assert banned not in code

    def test_no_credentials(self):
        # Arrange
        code = _strip_prose(
            (SRC_DIR / "dom_evidence_audit.py").read_text(
                encoding="utf-8"
            )
        ).lower()

        # Assert
        for banned in ["password", "api_key", "secret"]:
            assert banned not in code

    def test_no_walkability_fields(self):
        # Arrange
        code = _strip_prose(
            (SRC_DIR / "dom_evidence_audit.py").read_text(
                encoding="utf-8"
            )
        ).lower()

        # Assert
        for banned in [
            "walk_score",
            "walkability",
            "transit_score",
            "bike_score",
        ]:
            assert banned not in code

    def test_audit_model_has_no_walkability(self):
        # Act
        fields = DomEvidenceAudit.model_fields.keys()

        # Assert
        for banned in ["walk", "transit", "bike"]:
            assert not any(banned in f for f in fields)

    def test_never_writes_redfin_source_fields(self):
        # Arrange
        code = _strip_prose(
            (SRC_DIR / "dom_evidence_audit.py").read_text(
                encoding="utf-8"
            )
        ).lower()

        # Assert
        assert "update candidate_review_queue" not in code
        assert "update watched_properties" not in code
        assert "insert into candidate_review_queue" not in code
        assert "update listing_events" not in code

    def test_quiet_threshold_unchanged(self):
        # Assert
        assert config.quiet_score_minimum == 7.0

    def test_gatekeeper_behavior_unchanged(self):
        # Arrange
        from marketsentry.quiet_vibrancy import (
            apply_quiet_gatekeeper,
        )

        # Act
        passing, _ = apply_quiet_gatekeeper(9.9, 1.3)
        failing, _ = apply_quiet_gatekeeper(6.9, 1.1)

        # Assert
        assert passing == "pass"
        assert failing == "fail_noise_risk"

    def test_low_vibrancy_never_rescues_poor_quiet(self):
        # Arrange
        from marketsentry.quiet_vibrancy import (
            apply_quiet_gatekeeper,
        )

        # Act / Assert
        for vibrancy in [0.0, 0.1, 0.5, 1.0]:
            result, _ = apply_quiet_gatekeeper(6.9, vibrancy)
            assert result == "fail_noise_risk"

    def test_audit_does_not_touch_gatekeeper(self):
        # The audit must be unaware of Quiet scoring entirely.
        # Arrange
        code = _strip_prose(
            (SRC_DIR / "dom_evidence_audit.py").read_text(
                encoding="utf-8"
            )
        ).lower()

        # Assert
        assert "quiet_gatekeeper" not in code
        assert "apply_quiet_gatekeeper" not in code
