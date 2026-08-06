"""Milestone 54: manual Quiet/Vibrancy and noise-risk entry v2.

Covers score validation, gatekeeper explanations, per-candidate
score-entry status, the combined entry command, the manual score
queue export, backward compatibility of the M51 commands, and the
standing safety invariants.

All tests are local-only and perform no network calls.
"""

import inspect
import sqlite3
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from marketsentry.cli import app
from marketsentry.config import config
from marketsentry.manual_score_entry import (
    KNOWN_NOISE_SOURCES,
    LIFESTYLE_SCORE_MAX,
    LIFESTYLE_SCORE_MIN,
    NOISE_RISK_LEVELS,
    CandidateScoreEntryStatus,
    apply_scores_and_noise_notes,
    build_candidate_score_entry_status,
    build_gatekeeper_explanation,
    export_manual_score_entry_queue,
    extract_noise_risk_from_notes,
    extract_noise_sources_from_notes,
    list_candidate_score_entry_statuses,
    list_candidates_failing_gatekeeper,
    list_candidates_needing_scores,
    parse_noise_sources,
    summarize_manual_score_entry_queue,
    validate_lifestyle_score,
    validate_noise_risk,
)

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "marketsentry"

NEW_COMMANDS = [
    "candidate-score-status",
    "list-candidates-needing-scores",
    "candidate-score-and-noise-notes",
    "export-manual-score-entry-queue",
]


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


@pytest.fixture
def score_db(tmp_path):
    """Database with scored, unscored, and failing candidates."""
    db_path = str(tmp_path / "scores.db")
    from marketsentry.database import init_db

    init_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO candidate_review_queue "
        "(candidate_id, discovery_date, source_site, "
        "source_search_url, redfin_url, address, "
        "normalized_address, city, zip, quiet_score, "
        "vibrancy_score, quiet_gatekeeper_result, review_status, "
        "user_notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # Passing, watchlisted, no noise notes
            (
                4, "2026-08-01", "redfin", "",
                "https://www.redfin.com/CA/Temecula/"
                "32420-San-Marco-Dr-92592/home/6244468",
                "32420 San Marco Dr", "32420 san marco dr",
                "Temecula", "92592", 9.9, 1.3, "pass",
                "reviewed", None,
            ),
            # Failing gatekeeper with recorded noise knowledge
            (
                5, "2026-08-01", "redfin", "",
                "https://www.redfin.com/CA/Temecula/"
                "32152-Camino-Nunez-92592/home/6230280",
                "32152 Camino Nunez", "32152 camino nunez",
                "Temecula", "92592", 6.9, 1.1, "fail_noise_risk",
                "reviewed",
                "[Noise observation: risk=high] "
                "[Sources: traffic,airport,nighttime_racing] "
                "Track as noise-risk control.",
            ),
            # No scores at all
            (
                7, "2026-08-01", "redfin", "",
                "https://www.redfin.com/CA/Temecula/"
                "31801-Valone-Ct-92591/home/6242670",
                "31801 Valone Ct", "31801 valone ct",
                "Temecula", "92591", None, None, None,
                "pending", None,
            ),
        ],
    )
    conn.execute(
        "INSERT INTO watched_properties "
        "(property_id, first_saved_date, redfin_url, address, "
        "normalized_address, city, zip, quiet_score, "
        "vibrancy_score, active_watch_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            2, "2026-08-01",
            "https://www.redfin.com/CA/Temecula/"
            "32420-San-Marco-Dr-92592/home/6244468",
            "32420 San Marco Dr", "32420 san marco dr",
            "Temecula", "92592", 9.9, 1.3, 1,
        ),
    )
    conn.commit()
    conn.close()
    return db_path


class TestValidateLifestyleScore:
    """Score validation accepts the real range and rejects junk."""

    @pytest.mark.parametrize(
        "value", [0, 0.0, 7.0, 9.9, 10, 10.0, 5.5, "8.2"]
    )
    def test_accepts_valid_scores(self, value):
        # Act
        result = validate_lifestyle_score(value)

        # Assert
        assert result.is_valid is True
        assert result.value == float(value)

    @pytest.mark.parametrize(
        "value", [-1, -0.1, 10.1, 11, 100, -100]
    )
    def test_rejects_out_of_range(self, value):
        # Act
        result = validate_lifestyle_score(value)

        # Assert
        assert result.is_valid is False
        assert "outside the valid range" in result.error_message

    @pytest.mark.parametrize(
        "value", ["abc", "", "   ", None, [], {}]
    )
    def test_rejects_non_numeric(self, value):
        # Act
        result = validate_lifestyle_score(value)

        # Assert
        assert result.is_valid is False
        assert result.error_message

    def test_rejects_booleans(self):
        # Act
        result = validate_lifestyle_score(True)

        # Assert
        assert result.is_valid is False

    def test_rejects_infinity_and_nan(self):
        # Assert
        assert validate_lifestyle_score(
            float("inf")
        ).is_valid is False
        assert validate_lifestyle_score(
            float("nan")
        ).is_valid is False

    def test_boundaries_are_inclusive(self):
        # Assert
        assert validate_lifestyle_score(
            LIFESTYLE_SCORE_MIN
        ).is_valid is True
        assert validate_lifestyle_score(
            LIFESTYLE_SCORE_MAX
        ).is_valid is True

    def test_error_messages_are_operator_friendly(self):
        # Act
        result = validate_lifestyle_score("banana")

        # Assert
        assert "0.0 to 10.0" in result.error_message


class TestGatekeeperRules:
    """Quiet remains the gatekeeper at 7.0."""

    def test_quiet_7_0_passes(self):
        # Act
        explanation = build_gatekeeper_explanation(7.0, 2.0)

        # Assert
        assert explanation.result == "pass"
        assert explanation.passes is True

    def test_quiet_6_9_fails(self):
        # Act
        explanation = build_gatekeeper_explanation(6.9, 1.1)

        # Assert
        assert explanation.result == "fail_noise_risk"
        assert explanation.passes is False

    def test_low_vibrancy_does_not_override_quiet_6_9(self):
        # Act
        explanation = build_gatekeeper_explanation(6.9, 0.1)

        # Assert
        assert explanation.result == "fail_noise_risk"
        assert "does not override" in explanation.vibrancy_note

    def test_explanation_text_names_scores_and_threshold(self):
        # Act
        explanation = build_gatekeeper_explanation(6.9, 1.1)

        # Assert
        assert "6.9" in explanation.explanation
        assert "7.0" in explanation.explanation
        assert "fail_noise_risk" in explanation.explanation
        assert "1.1" in explanation.explanation

    def test_passing_explanation_notes_vibrancy_is_not_gate(self):
        # Act
        explanation = build_gatekeeper_explanation(9.9, 1.3)

        # Assert
        assert "passes" in explanation.explanation
        assert "not a gatekeeper" in explanation.vibrancy_note

    def test_missing_quiet_reports_no_data(self):
        # Act
        explanation = build_gatekeeper_explanation(None, 1.0)

        # Assert
        assert explanation.result == "fail_no_data"
        assert explanation.passes is False

    def test_threshold_comes_from_config(self):
        # Act
        explanation = build_gatekeeper_explanation(8.0, 1.0)

        # Assert
        assert explanation.threshold == config.quiet_score_minimum
        assert explanation.threshold == 7.0


class TestNoiseHelpers:
    """Noise risk validation and source parsing."""

    @pytest.mark.parametrize("level", NOISE_RISK_LEVELS)
    def test_accepts_valid_levels(self, level):
        # Act
        result = validate_noise_risk(level)

        # Assert
        assert result.is_valid is True
        assert result.value == level

    def test_rejects_invalid_level(self):
        # Act
        result = validate_noise_risk("extreme")

        # Assert
        assert result.is_valid is False
        assert "not a noise risk level" in result.error_message

    def test_blank_defaults_to_unknown(self):
        # Act
        result = validate_noise_risk(None)

        # Assert
        assert result.is_valid is True
        assert result.value == "unknown"

    def test_normalizes_case(self):
        # Act
        result = validate_noise_risk("  HIGH  ")

        # Assert
        assert result.is_valid is True
        assert result.value == "high"

    def test_parse_sources_splits_and_normalizes(self):
        # Act
        sources = parse_noise_sources(
            "traffic, Airport ,nighttime racing"
        )

        # Assert
        assert sources == [
            "traffic", "airport", "nighttime_racing"
        ]

    def test_parse_sources_deduplicates_preserving_order(self):
        # Act
        sources = parse_noise_sources(
            "airport,traffic,airport"
        )

        # Assert
        assert sources == ["airport", "traffic"]

    def test_parse_sources_accepts_list(self):
        # Act
        sources = parse_noise_sources(["traffic", "school"])

        # Assert
        assert sources == ["traffic", "school"]

    def test_parse_sources_empty_returns_empty(self):
        # Assert
        assert parse_noise_sources(None) == []
        assert parse_noise_sources("") == []
        assert parse_noise_sources(" , , ") == []

    def test_unrecognized_source_is_preserved(self):
        # Local field knowledge must never be silently discarded.
        # Act
        sources = parse_noise_sources("quarry_blasting")

        # Assert
        assert sources == ["quarry_blasting"]

    def test_known_sources_list_covers_dashboard_options(self):
        # Assert
        for expected in [
            "traffic", "airport", "road", "freeway",
            "nighttime_racing", "school", "commercial",
            "unknown", "other",
        ]:
            assert expected in KNOWN_NOISE_SOURCES


class TestNoiseNoteExtraction:
    """Noise data is recovered from the existing notes field."""

    def test_extracts_risk(self):
        # Act
        risk = extract_noise_risk_from_notes(
            "[Noise observation: risk=high] [Sources: traffic] x"
        )

        # Assert
        assert risk == "high"

    def test_extracts_sources(self):
        # Act
        sources = extract_noise_sources_from_notes(
            "[Noise observation: risk=high] "
            "[Sources: traffic,airport] x"
        )

        # Assert
        assert sources == ["traffic", "airport"]

    def test_uses_most_recent_observation(self):
        # Act
        risk = extract_noise_risk_from_notes(
            "[Noise observation: risk=low] older\n"
            "[Noise observation: risk=severe] newer"
        )

        # Assert
        assert risk == "severe"

    def test_returns_none_when_absent(self):
        # Assert
        assert extract_noise_risk_from_notes(None) is None
        assert extract_noise_risk_from_notes("plain note") is None
        assert extract_noise_sources_from_notes("plain") == []


class TestCandidateScoreEntryStatus:
    """Per-candidate status reflects real database state."""

    def test_candidate_with_no_scores(self, score_db):
        # Act
        status = build_candidate_score_entry_status(7, score_db)

        # Assert
        assert status is not None
        assert status.needs_quiet_vibrancy is True
        assert status.quiet_score is None
        assert "quiet_score" in status.missing_fields
        assert "vibrancy_score" in status.missing_fields
        assert "read Quiet and Vibrancy" in (
            status.recommended_next_step
        )

    def test_candidate_with_passing_scores(self, score_db):
        # Act
        status = build_candidate_score_entry_status(4, score_db)

        # Assert
        assert status.needs_quiet_vibrancy is False
        assert status.is_gatekeeper_fail is False
        assert status.quiet_gatekeeper_result == "pass"
        assert status.is_watchlisted is True

    def test_candidate_with_failing_scores(self, score_db):
        # Act
        status = build_candidate_score_entry_status(5, score_db)

        # Assert
        assert status.is_gatekeeper_fail is True
        assert status.quiet_score == 6.9
        assert status.noise_risk == "high"
        assert "traffic" in status.noise_sources
        assert "noise-risk control" in (
            status.recommended_next_step
        )

    def test_missing_candidate_returns_none(self, score_db):
        # Assert
        assert build_candidate_score_entry_status(
            999, score_db
        ) is None

    def test_missing_database_returns_none(self, tmp_path):
        # Assert
        assert build_candidate_score_entry_status(
            1, str(tmp_path / "absent.db")
        ) is None

    def test_status_is_read_only(self, score_db):
        # Arrange
        conn = sqlite3.connect(score_db)
        before = conn.execute(
            "SELECT quiet_score, user_notes FROM "
            "candidate_review_queue WHERE candidate_id = 5"
        ).fetchone()
        conn.close()

        # Act
        build_candidate_score_entry_status(5, score_db)
        list_candidate_score_entry_statuses(score_db)

        # Assert
        conn = sqlite3.connect(score_db)
        after = conn.execute(
            "SELECT quiet_score, user_notes FROM "
            "candidate_review_queue WHERE candidate_id = 5"
        ).fetchone()
        conn.close()
        assert before == after


class TestListingCandidates:
    """Listing helpers select the right candidates."""

    def test_lists_candidates_needing_scores(self, score_db):
        # Act
        statuses = list_candidates_needing_scores(score_db)

        # Assert
        assert [s.candidate_id for s in statuses] == [7]

    def test_include_noise_widens_the_list(self, score_db):
        # Act
        statuses = list_candidates_needing_scores(
            score_db, include_missing_noise_notes=True
        )

        # Assert: candidate 4 has scores but no noise observation
        ids = sorted(s.candidate_id for s in statuses)
        assert ids == [4, 7]

    def test_lists_candidates_failing_gatekeeper(self, score_db):
        # Act
        statuses = list_candidates_failing_gatekeeper(score_db)

        # Assert
        assert [s.candidate_id for s in statuses] == [5]

    def test_summary_counts(self, score_db):
        # Act
        summary = summarize_manual_score_entry_queue(score_db)

        # Assert
        assert summary["total_candidates"] == 3
        assert summary["needing_quiet_vibrancy"] == 1
        assert summary["failing_gatekeeper"] == 1
        assert summary["watchlisted"] == 1


class TestCombinedEntry:
    """Combined score and noise entry validates before writing."""

    def test_applies_scores_and_notes(self, score_db):
        # Act
        result = apply_scores_and_noise_notes(
            candidate_id=7,
            quiet_score=8.5,
            vibrancy_score=1.9,
            noise_risk="low",
            noise_sources="traffic",
            notes="Quiet cul-de-sac",
            db_path=score_db,
        )

        # Assert
        assert result.success is True
        assert result.scores_applied is True
        assert result.noise_notes_applied is True

        status = build_candidate_score_entry_status(7, score_db)
        assert status.quiet_score == 8.5
        assert status.vibrancy_score == 1.9
        assert status.noise_risk == "low"

    def test_applies_gatekeeper_on_write(self, score_db):
        # Act
        apply_scores_and_noise_notes(
            candidate_id=7,
            quiet_score=6.5,
            vibrancy_score=0.5,
            db_path=score_db,
        )

        # Assert
        status = build_candidate_score_entry_status(7, score_db)
        assert status.quiet_gatekeeper_result == "fail_noise_risk"

    def test_invalid_score_applies_nothing(self, score_db):
        # Act
        result = apply_scores_and_noise_notes(
            candidate_id=7,
            quiet_score=15,
            vibrancy_score=1.0,
            noise_risk="high",
            notes="should not be written",
            db_path=score_db,
        )

        # Assert: validation fails before any write
        assert result.success is False
        assert result.scores_applied is False
        assert result.noise_notes_applied is False

        status = build_candidate_score_entry_status(7, score_db)
        assert status.quiet_score is None
        assert status.noise_risk is None

    def test_invalid_noise_risk_applies_nothing(self, score_db):
        # Act
        result = apply_scores_and_noise_notes(
            candidate_id=7,
            quiet_score=8.0,
            vibrancy_score=1.0,
            noise_risk="extreme",
            db_path=score_db,
        )

        # Assert
        assert result.success is False
        status = build_candidate_score_entry_status(7, score_db)
        assert status.quiet_score is None

    def test_requires_both_scores_together(self, score_db):
        # Act
        result = apply_scores_and_noise_notes(
            candidate_id=7,
            quiet_score=8.0,
            db_path=score_db,
        )

        # Assert
        assert result.success is False
        assert any(
            "both Quiet and Vibrancy" in e for e in result.errors
        )

    def test_noise_only_entry_is_allowed(self, score_db):
        # Act
        result = apply_scores_and_noise_notes(
            candidate_id=4,
            noise_risk="moderate",
            noise_sources="traffic,school",
            db_path=score_db,
        )

        # Assert
        assert result.success is True
        assert result.scores_applied is False
        assert result.noise_notes_applied is True

    def test_empty_request_is_rejected(self, score_db):
        # Act
        result = apply_scores_and_noise_notes(
            candidate_id=7, db_path=score_db
        )

        # Assert
        assert result.success is False
        assert result.errors

    def test_missing_candidate_reports_error(self, score_db):
        # Act
        result = apply_scores_and_noise_notes(
            candidate_id=999,
            quiet_score=8.0,
            vibrancy_score=1.0,
            db_path=score_db,
        )

        # Assert
        assert result.success is False
        assert any("not found" in e for e in result.errors)

    def test_existing_notes_are_preserved(self, score_db):
        # Act
        apply_scores_and_noise_notes(
            candidate_id=5,
            noise_risk="severe",
            notes="Additional observation",
            db_path=score_db,
        )

        # Assert
        status = build_candidate_score_entry_status(5, score_db)
        assert "Track as noise-risk control." in status.user_notes
        assert "Additional observation" in status.user_notes

    def test_refresh_not_run_by_default(
        self, score_db, monkeypatch
    ):
        # Arrange
        def _spy(*args, **kwargs):
            raise AssertionError("refresh should not run")

        monkeypatch.setattr(
            "marketsentry.operator_workflow."
            "run_operator_refresh_workflow",
            _spy,
        )

        # Act
        result = apply_scores_and_noise_notes(
            candidate_id=7,
            quiet_score=8.0,
            vibrancy_score=1.0,
            db_path=score_db,
        )

        # Assert
        assert result.success is True
        assert result.refresh_ran is False

    def test_refresh_failure_does_not_undo_writes(
        self, score_db, monkeypatch
    ):
        # Arrange
        def _boom(*args, **kwargs):
            raise RuntimeError("refresh exploded")

        monkeypatch.setattr(
            "marketsentry.operator_workflow."
            "run_operator_refresh_workflow",
            _boom,
        )

        # Act
        result = apply_scores_and_noise_notes(
            candidate_id=7,
            quiet_score=8.0,
            vibrancy_score=1.0,
            db_path=score_db,
            refresh=True,
        )

        # Assert
        assert result.scores_applied is True
        assert result.refresh_ran is False
        assert "refresh exploded" in result.refresh_error

        status = build_candidate_score_entry_status(7, score_db)
        assert status.quiet_score == 8.0


class TestExportManualScoreQueue:
    """Manual score entry queue export."""

    def test_csv_export(self, score_db, tmp_path):
        # Act
        paths = export_manual_score_entry_queue(
            db_path=score_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="csv",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert len(paths) == 1
        assert paths[0].endswith(".csv")
        for column in [
            "candidate_id",
            "quiet_score",
            "vibrancy_score",
            "quiet_gatekeeper_result",
            "noise_risk",
            "noise_sources",
            "missing_fields",
            "recommended_next_step",
            "redfin_url",
        ]:
            assert column in content

    def test_markdown_export(self, score_db, tmp_path):
        # Act
        paths = export_manual_score_entry_queue(
            db_path=score_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert "# Manual Score Entry Queue" in content
        assert "gatekeeper" in content.lower()

    def test_markdown_has_clickable_links(
        self, score_db, tmp_path
    ):
        # Act
        paths = export_manual_score_entry_queue(
            db_path=score_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert "[View](" in content
        assert "redfin.com" in content

    def test_export_both_formats(self, score_db, tmp_path):
        # Act
        paths = export_manual_score_entry_queue(
            db_path=score_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="both",
        )

        # Assert
        assert len(paths) == 2

    def test_outstanding_only_by_default(
        self, score_db, tmp_path
    ):
        # Act
        paths = export_manual_score_entry_queue(
            db_path=score_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="csv",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert: candidates 4, 5, 7 all have outstanding work
        assert "Camino Nunez" in content
        assert "Valone Ct" in content

    def test_export_states_gatekeeper_rule(
        self, score_db, tmp_path
    ):
        # Act
        paths = export_manual_score_entry_queue(
            db_path=score_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert "does not override" in content

    def test_export_makes_no_purchase_recommendation(
        self, score_db, tmp_path
    ):
        # Act
        paths = export_manual_score_entry_queue(
            db_path=score_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
        )
        content = Path(paths[0]).read_text(encoding="utf-8").lower()

        # Assert
        for banned in ["you should buy", "recommend buying"]:
            assert banned not in content

    def test_export_does_not_mutate(self, score_db, tmp_path):
        # Arrange
        conn = sqlite3.connect(score_db)
        before = conn.execute(
            "SELECT COUNT(*), SUM(COALESCE(quiet_score, 0)) "
            "FROM candidate_review_queue"
        ).fetchone()
        conn.close()

        # Act
        export_manual_score_entry_queue(
            db_path=score_db,
            exports_dir=str(tmp_path / "exports"),
        )

        # Assert
        conn = sqlite3.connect(score_db)
        after = conn.execute(
            "SELECT COUNT(*), SUM(COALESCE(quiet_score, 0)) "
            "FROM candidate_review_queue"
        ).fetchone()
        conn.close()
        assert before == after


class TestBackwardCompatibility:
    """M51 commands keep working exactly as before."""

    def test_apply_candidate_location_scores_unchanged(
        self, score_db
    ):
        # Arrange
        from marketsentry.operator_workflow import (
            apply_candidate_location_scores,
        )

        # Act
        result = apply_candidate_location_scores(
            candidate_id=7,
            quiet_score=9.5,
            vibrancy_score=1.2,
            db_path=score_db,
        )

        # Assert
        assert result.success is True
        status = build_candidate_score_entry_status(7, score_db)
        assert status.quiet_score == 9.5
        assert status.quiet_gatekeeper_result == "pass"

    def test_apply_candidate_noise_notes_unchanged(
        self, score_db
    ):
        # Arrange
        from marketsentry.operator_workflow import (
            apply_candidate_noise_notes,
        )

        # Act
        result = apply_candidate_noise_notes(
            candidate_id=7,
            noise_risk="moderate",
            noise_sources="traffic",
            notes="Field observation",
            db_path=score_db,
        )

        # Assert
        assert result.success is True
        status = build_candidate_score_entry_status(7, score_db)
        assert status.noise_risk == "moderate"

    def test_cli_candidate_location_scores_still_works(
        self, score_db
    ):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "candidate-location-scores",
                "--candidate-id", "7",
                "--quiet-score", "8.8",
                "--vibrancy-score", "1.5",
                "--db", score_db,
            ],
        )

        # Assert
        assert result.exit_code == 0

    def test_cli_candidate_noise_notes_still_works(self, score_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "candidate-noise-notes",
                "--candidate-id", "7",
                "--noise-risk", "high",
                "--noise-sources", "traffic,airport",
                "--db", score_db,
            ],
        )

        # Assert
        assert result.exit_code == 0


class TestNewCliCommands:
    """New CLI surface."""

    @pytest.mark.parametrize("command_name", NEW_COMMANDS)
    def test_command_registered(self, command_name):
        # Assert
        assert command_name in _command_map()

    @pytest.mark.parametrize("command_name", NEW_COMMANDS)
    def test_command_uses_canonical_db_default(self, command_name):
        # Act
        default = _db_default(_command_map()[command_name])

        # Assert
        assert default == config.database_path
        assert default == "db/marketsentry.db"

    def test_candidate_score_status_output(self, score_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "candidate-score-status",
                "--candidate-id", "5",
                "--db", score_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "fail_noise_risk" in result.output
        assert "gatekeeper" in result.output.lower()

    def test_candidate_score_status_missing_candidate(
        self, score_db
    ):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "candidate-score-status",
                "--candidate-id", "999",
                "--db", score_db,
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_list_candidates_needing_scores_output(
        self, score_db
    ):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "list-candidates-needing-scores",
                "--db", score_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Missing Quiet/Vibrancy" in result.output

    def test_combined_command_rejects_bad_score(self, score_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "candidate-score-and-noise-notes",
                "--candidate-id", "7",
                "--quiet-score", "15",
                "--vibrancy-score", "1.0",
                "--db", score_db,
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "No changes applied" in result.output

        status = build_candidate_score_entry_status(7, score_db)
        assert status.quiet_score is None

    def test_combined_command_applies_valid_entry(self, score_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "candidate-score-and-noise-notes",
                "--candidate-id", "7",
                "--quiet-score", "9.1",
                "--vibrancy-score", "1.4",
                "--noise-risk", "low",
                "--db", score_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        status = build_candidate_score_entry_status(7, score_db)
        assert status.quiet_score == 9.1

    def test_export_command_runs(self, score_db, tmp_path):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "export-manual-score-entry-queue",
                "--db", score_db,
                "--output-dir", str(tmp_path / "exports"),
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Exported" in result.output

    def test_custom_db_accepted(self, score_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "list-candidates-needing-scores",
                "--db", score_db,
            ],
        )

        # Assert
        assert "No such option" not in result.output
        assert result.exit_code == 0


class TestNextStepIntegration:
    """Next steps name the specific candidates."""

    def test_screening_next_steps_names_failing_candidate(
        self, score_db
    ):
        # Arrange
        from marketsentry.redfin_screening_queue import (
            build_screening_next_steps,
        )

        # Act
        steps = build_screening_next_steps(db_path=score_db)
        gatekeeper_steps = [
            s for s in steps if s.step_id == "review_noise_risk"
        ]

        # Assert
        assert gatekeeper_steps
        assert "Candidate 5" in gatekeeper_steps[0].message

    def test_screening_next_steps_names_unscored_candidate(
        self, score_db
    ):
        # Arrange
        from marketsentry.redfin_screening_queue import (
            build_screening_next_steps,
        )

        # Act
        steps = build_screening_next_steps(db_path=score_db)
        score_steps = [
            s
            for s in steps
            if s.step_id == "capture_quiet_vibrancy"
        ]

        # Assert
        assert score_steps
        assert "Candidate 7" in score_steps[0].message


class TestDashboardSection:
    """Dashboard exposes the manual entry section."""

    def test_section_present(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "Manual Quiet/Vibrancy Entry" in content
        assert "manual_score_entry_form" in content

    def test_gatekeeper_preview_present(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "mse_preview_quiet" in content
        assert "build_gatekeeper_explanation" in content

    def test_noise_controls_present(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "mse_risk" in content
        assert "mse_sources" in content
        assert "mse_refresh" in content

    def test_export_form_present(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "manual_score_export_form" in content

    def test_mutations_only_inside_submit_branches(self):
        # Arrange: every write call must sit after a submit guard,
        # so rendering the section cannot mutate the database.
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")
        lines = content.split("\n")

        submit_lines = [
            i
            for i, line in enumerate(lines)
            if "if _mse_submit:" in line
            or "if _mse_export_submit:" in line
        ]
        write_lines = [
            i
            for i, line in enumerate(lines)
            if "apply_scores_and_noise_notes(" in line
            or "export_manual_score_entry_queue(" in line
        ]

        # Assert
        assert submit_lines
        # Ignore the import block at the top of the section.
        write_lines = [
            i
            for i in write_lines
            if not lines[i].strip().startswith(
                ("apply_scores_and_noise_notes,",
                 "export_manual_score_entry_queue,")
            )
        ]
        assert write_lines
        for write_line in write_lines:
            assert any(
                submit_line < write_line
                for submit_line in submit_lines
            ), f"unguarded write at line {write_line + 1}"

    def test_dashboard_imports(self):
        # Act
        import marketsentry.dashboard_app as dash

        # Assert
        assert dash is not None


class TestSafetyInvariants:
    """Milestone 54 adds no unsafe capability."""

    def test_no_network_imports(self):
        # Arrange
        source = (
            SRC_DIR / "manual_score_entry.py"
        ).read_text(encoding="utf-8")

        # Assert
        for banned in [
            "import requests",
            "import httpx",
            "urllib.request",
            "playwright",
            "selenium",
            "smtplib",
            "webbrowser",
            "BeautifulSoup",
        ]:
            assert banned not in source

    def test_no_outbound_notifications(self):
        # Arrange
        source = (
            SRC_DIR / "manual_score_entry.py"
        ).read_text(encoding="utf-8")

        # Assert
        for banned in ["smtp", "send_email", "webhook", "sms"]:
            assert banned not in source.lower()

    def test_no_credentials(self):
        # Arrange
        source = (
            SRC_DIR / "manual_score_entry.py"
        ).read_text(encoding="utf-8")

        # Assert
        for banned in ["password", "api_key", "secret"]:
            assert banned not in source.lower()

    def test_no_walkability_fields(self):
        # Arrange
        source = (
            SRC_DIR / "manual_score_entry.py"
        ).read_text(encoding="utf-8")

        # Assert
        for banned in [
            "walk_score", "transit_score", "bike_score",
        ]:
            assert banned not in source.lower()

    def test_no_redfin_page_parsing(self):
        # This milestone must not read Redfin pages.
        # Arrange
        source = (
            SRC_DIR / "manual_score_entry.py"
        ).read_text(encoding="utf-8")

        # Assert
        for banned in [
            "LifestyleScoreCard",
            "html.parser",
            "lxml",
            "find_all",
        ]:
            assert banned not in source

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

    def test_status_model_has_no_walkability_field(self):
        # Act
        fields = CandidateScoreEntryStatus.model_fields.keys()

        # Assert
        for banned in ["walk_score", "walkability", "transit"]:
            assert not any(banned in f for f in fields)
