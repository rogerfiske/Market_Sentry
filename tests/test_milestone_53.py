"""Milestone 53: screening queue batch actions and refresh integration.

Covers ID parsing, the four batch actions, next-step guidance, the
optional local refresh, export enrichment, and the standing safety
invariants.

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
from marketsentry.redfin_screening_queue import (
    RedfinScreeningBatchActionRequest,
    RedfinScreeningBatchActionResult,
    RedfinScreeningNextStep,
    RedfinScreeningOperatorStatus,
    batch_hold_screening_items,
    batch_mark_screening_items_opened,
    batch_reject_screening_items,
    batch_save_screening_items_for_analysis,
    build_screening_next_steps,
    build_screening_report_rows,
    ensure_redfin_screening_queue_schema,
    export_redfin_screening_queue,
    list_redfin_screening_items,
    parse_screening_id_list,
    summarize_screening_operator_status,
)

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "marketsentry"

BATCH_COMMANDS = [
    "batch-save-screening-items",
    "batch-reject-screening-items",
    "batch-hold-screening-items",
    "batch-mark-screening-items-opened",
    "screening-next-steps",
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


def _insert_item(db_path, screening_id, address, url, status="new"):
    """Insert one screening item directly."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO redfin_screening_queue "
        "(screening_id, redfin_url, normalized_redfin_url, "
        "address, city, status, user_screening_decision) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (screening_id, url, url, address, "Temecula", status, status),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def screening_db(tmp_path):
    """Database with three real-looking screening items."""
    db_path = str(tmp_path / "screening.db")
    ensure_redfin_screening_queue_schema(db_path=db_path)

    from marketsentry.database import init_db

    init_db(db_path)

    _insert_item(
        db_path,
        4,
        "31801 Valone Ct",
        "https://www.redfin.com/CA/Temecula/"
        "31801-Valone-Ct-92591/home/6242670",
    )
    _insert_item(
        db_path,
        5,
        "31457 Britton Cir",
        "https://www.redfin.com/CA/Temecula/"
        "31457-Britton-Cir-92591/home/6226452",
    )
    _insert_item(
        db_path,
        6,
        "41451 Royal Dornoch Ct",
        "https://www.redfin.com/CA/Temecula/"
        "41451-Royal-Dornoch-Ct-92591/home/6361262",
    )
    return db_path


class TestParseScreeningIdList:
    """Comma-separated ID parsing."""

    def test_parses_simple_list(self):
        # Act
        ids, invalid, dupes = parse_screening_id_list("4,5,6")

        # Assert
        assert ids == [4, 5, 6]
        assert invalid == []
        assert dupes == []

    def test_tolerates_whitespace(self):
        # Act
        ids, _, _ = parse_screening_id_list(" 4 , 5 ,6 ")

        # Assert
        assert ids == [4, 5, 6]

    def test_reports_duplicates_without_actioning_twice(self):
        # Act
        ids, _, dupes = parse_screening_id_list("4,5,4,6,5")

        # Assert
        assert ids == [4, 5, 6]
        assert dupes == [4, 5]

    def test_reports_invalid_entries(self):
        # Act
        ids, invalid, _ = parse_screening_id_list("4,abc,6,")

        # Assert
        assert ids == [4, 6]
        assert invalid == ["abc"]

    def test_empty_string_returns_empty(self):
        # Act
        ids, invalid, dupes = parse_screening_id_list("")

        # Assert
        assert ids == []
        assert invalid == []
        assert dupes == []

    def test_none_returns_empty(self):
        # Act
        ids, invalid, dupes = parse_screening_id_list(None)

        # Assert
        assert ids == []
        assert invalid == []
        assert dupes == []

    def test_only_separators_returns_empty(self):
        # Act
        ids, invalid, _ = parse_screening_id_list(",,, ,")

        # Assert
        assert ids == []
        assert invalid == []


class TestBatchMarkOpened:
    """Batch mark opened."""

    def test_marks_all_supplied_items(self, screening_db):
        # Act
        result = batch_mark_screening_items_opened(
            [4, 5, 6], db_path=screening_db
        )

        # Assert
        assert result.succeeded_count == 3
        assert result.failed_count == 0
        items = list_redfin_screening_items(db_path=screening_db)
        assert all(i.status == "opened" for i in items)

    def test_missing_id_reported_but_others_processed(
        self, screening_db
    ):
        # Act
        result = batch_mark_screening_items_opened(
            [4, 999, 6], db_path=screening_db
        )

        # Assert
        assert result.missing_ids == [999]
        assert result.succeeded_count == 2
        assert result.failed_count == 1

    def test_empty_list_reports_error(self, screening_db):
        # Act
        result = batch_mark_screening_items_opened(
            [], db_path=screening_db
        )

        # Assert
        assert result.item_results == []
        assert result.errors


class TestBatchReject:
    """Batch reject."""

    def test_rejects_all_items(self, screening_db):
        # Act
        result = batch_reject_screening_items(
            [4, 5], notes="Too close to arterial road",
            db_path=screening_db,
        )

        # Assert
        assert result.succeeded_count == 2
        items = {
            i.screening_id: i
            for i in list_redfin_screening_items(
                db_path=screening_db
            )
        }
        assert items[4].status == "rejected"
        assert items[5].status == "rejected"
        assert items[6].status == "new"

    def test_preserves_notes(self, screening_db):
        # Act
        batch_reject_screening_items(
            [4], notes="First note", db_path=screening_db
        )
        batch_reject_screening_items(
            [4], notes="Second note", db_path=screening_db
        )

        # Assert
        items = {
            i.screening_id: i
            for i in list_redfin_screening_items(
                db_path=screening_db
            )
        }
        assert "First note" in items[4].user_notes
        assert "Second note" in items[4].user_notes


class TestBatchHold:
    """Batch hold."""

    def test_holds_all_items(self, screening_db):
        # Act
        result = batch_hold_screening_items(
            [5, 6], notes="Wait for price reduction",
            db_path=screening_db,
        )

        # Assert
        assert result.succeeded_count == 2
        items = {
            i.screening_id: i
            for i in list_redfin_screening_items(
                db_path=screening_db
            )
        }
        assert items[5].status == "hold"
        assert items[6].status == "hold"

    def test_notes_recorded(self, screening_db):
        # Act
        batch_hold_screening_items(
            [5], notes="Need more noise data",
            db_path=screening_db,
        )

        # Assert
        items = {
            i.screening_id: i
            for i in list_redfin_screening_items(
                db_path=screening_db
            )
        }
        assert "Need more noise data" in items[5].user_notes


class TestBatchSaveForAnalysis:
    """Batch Save for Analysis creates and links candidates."""

    def test_creates_candidates(self, screening_db):
        # Act
        result = batch_save_screening_items_for_analysis(
            [4, 5, 6], db_path=screening_db
        )

        # Assert
        assert result.succeeded_count == 3
        assert len(result.created_candidate_ids) == 3

        conn = sqlite3.connect(screening_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert count == 3

    def test_marks_items_saved_and_links_candidate(
        self, screening_db
    ):
        # Act
        batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )

        # Assert
        items = {
            i.screening_id: i
            for i in list_redfin_screening_items(
                db_path=screening_db
            )
        }
        assert items[4].status == "saved_for_analysis"
        assert items[4].candidate_id is not None

    def test_does_not_duplicate_candidates_on_resave(
        self, screening_db
    ):
        # Arrange
        first = batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )

        # Act
        second = batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )

        # Assert
        conn = sqlite3.connect(screening_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert count == 1
        assert (
            first.created_candidate_ids
            == second.created_candidate_ids
        )

    def test_links_existing_candidate_by_url(self, screening_db):
        # Arrange: a candidate already exists for the same URL
        from marketsentry.database import insert_candidate
        from marketsentry.models import CandidateProperty

        existing_id = insert_candidate(
            CandidateProperty(
                source_site="redfin",
                source_search_url="",
                redfin_url=(
                    "https://www.redfin.com/CA/Temecula/"
                    "31801-Valone-Ct-92591/home/6242670"
                ),
                address="31801 Valone Ct",
                city="Temecula",
            ),
            skip_if_exists=True,
            database_path=screening_db,
        )

        # Act
        result = batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )

        # Assert
        assert result.created_candidate_ids == [existing_id]
        conn = sqlite3.connect(screening_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_preserves_notes(self, screening_db):
        # Act
        batch_save_screening_items_for_analysis(
            [4], notes="Worth deeper analysis",
            db_path=screening_db,
        )

        # Assert
        items = {
            i.screening_id: i
            for i in list_redfin_screening_items(
                db_path=screening_db
            )
        }
        assert "Worth deeper analysis" in items[4].user_notes

    def test_partial_failure_does_not_block_others(
        self, screening_db
    ):
        # Act
        result = batch_save_screening_items_for_analysis(
            [4, 999, 6], db_path=screening_db
        )

        # Assert
        assert result.succeeded_count == 2
        assert result.failed_count == 1
        assert result.missing_ids == [999]

        conn = sqlite3.connect(screening_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert count == 2

    def test_per_item_results_reported(self, screening_db):
        # Act
        result = batch_save_screening_items_for_analysis(
            [4, 999], db_path=screening_db
        )

        # Assert
        by_id = {r.screening_id: r for r in result.item_results}
        assert by_id[4].success is True
        assert by_id[999].success is False
        assert "not found" in by_id[999].detail


class TestRefreshIntegration:
    """Optional local refresh after Save for Analysis."""

    def test_refresh_not_run_by_default(
        self, screening_db, monkeypatch
    ):
        # Arrange
        called = {"count": 0}

        def _spy(*args, **kwargs):
            called["count"] += 1
            raise AssertionError("refresh should not run")

        monkeypatch.setattr(
            "marketsentry.operator_workflow."
            "run_operator_refresh_workflow",
            _spy,
        )

        # Act
        result = batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )

        # Assert
        assert called["count"] == 0
        assert result.refresh_requested is False
        assert result.refresh_ran is False

    def test_refresh_runs_only_when_requested(
        self, screening_db, monkeypatch, tmp_path
    ):
        # Arrange
        called = {"count": 0}

        class _Run:
            output_paths = ["data/exports/example_report.md"]

        def _spy(*args, **kwargs):
            called["count"] += 1
            return _Run()

        monkeypatch.setattr(
            "marketsentry.operator_workflow."
            "run_operator_refresh_workflow",
            _spy,
        )

        # Act
        result = batch_save_screening_items_for_analysis(
            [4],
            db_path=screening_db,
            refresh=True,
            exports_dir=str(tmp_path / "exports"),
        )

        # Assert
        assert called["count"] == 1
        assert result.refresh_ran is True
        assert result.refresh_output_paths == [
            "data/exports/example_report.md"
        ]

    def test_refresh_failure_does_not_roll_back_saves(
        self, screening_db, monkeypatch
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
        result = batch_save_screening_items_for_analysis(
            [4, 5], db_path=screening_db, refresh=True
        )

        # Assert: saves stand, refresh error is reported
        assert result.succeeded_count == 2
        assert result.refresh_ran is False
        assert "refresh exploded" in result.refresh_error

        items = {
            i.screening_id: i
            for i in list_redfin_screening_items(
                db_path=screening_db
            )
        }
        assert items[4].status == "saved_for_analysis"
        assert items[5].status == "saved_for_analysis"

    def test_non_save_batches_never_refresh(self, screening_db):
        # Act
        result = batch_reject_screening_items(
            [4], db_path=screening_db
        )

        # Assert
        assert result.refresh_requested is False
        assert result.refresh_ran is False


class TestNextSteps:
    """Next-step guidance."""

    def test_new_items_prompt_inspection(self, screening_db):
        # Act
        steps = build_screening_next_steps(db_path=screening_db)

        # Assert
        ids = [s.step_id for s in steps]
        assert "open_new_items" in ids

    def test_opened_items_prompt_decision(self, screening_db):
        # Arrange
        batch_mark_screening_items_opened(
            [4, 5, 6], db_path=screening_db
        )

        # Act
        steps = build_screening_next_steps(db_path=screening_db)

        # Assert
        ids = [s.step_id for s in steps]
        assert "decide_opened_items" in ids

    def test_saved_without_enrichment_prompts_detail_html(
        self, screening_db
    ):
        # Arrange
        batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )

        # Act
        steps = build_screening_next_steps(db_path=screening_db)

        # Assert
        ids = [s.step_id for s in steps]
        assert "save_detail_html" in ids

    def test_empty_queue_suggests_import(self, tmp_path):
        # Arrange
        db_path = str(tmp_path / "empty.db")
        ensure_redfin_screening_queue_schema(db_path=db_path)

        # Act
        steps = build_screening_next_steps(db_path=db_path)

        # Assert
        assert steps[0].step_id == "import_screening_urls"

    def test_steps_make_no_purchase_recommendation(
        self, screening_db
    ):
        # Act
        steps = build_screening_next_steps(db_path=screening_db)

        # Assert
        banned = ["buy", "offer", "bid", "purchase", "invest"]
        for step in steps:
            lowered = step.message.lower()
            for word in banned:
                assert word not in lowered

    def test_operator_status_summarizes_queue(self, screening_db):
        # Act
        status = summarize_screening_operator_status(
            db_path=screening_db
        )

        # Assert
        assert isinstance(status, RedfinScreeningOperatorStatus)
        assert status.queue.total == 3
        assert status.queue.new == 3

    def test_operator_status_warns_on_missing_enrichment(
        self, screening_db
    ):
        # Arrange
        batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )

        # Act
        status = summarize_screening_operator_status(
            db_path=screening_db
        )

        # Assert
        assert status.saved_missing_enrichment == 1
        assert any(
            "enrichment" in w.lower() for w in status.warnings
        )


class TestExportEnrichment:
    """Export includes candidate status and next steps."""

    def test_csv_includes_new_columns(self, screening_db, tmp_path):
        # Act
        paths = export_redfin_screening_queue(
            db_path=screening_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="csv",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        for column in [
            "saved_for_analysis",
            "candidate_has_enrichment",
            "candidate_has_quiet_vibrancy",
            "candidate_watchlisted",
            "next_step",
        ]:
            assert column in content

    def test_markdown_includes_next_steps_section(
        self, screening_db, tmp_path
    ):
        # Act
        paths = export_redfin_screening_queue(
            db_path=screening_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert "## Next Steps" in content
        assert "Next Step" in content

    def test_markdown_keeps_clickable_links(
        self, screening_db, tmp_path
    ):
        # Act
        paths = export_redfin_screening_queue(
            db_path=screening_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert "[View](" in content

    def test_report_rows_reflect_candidate_state(
        self, screening_db
    ):
        # Arrange
        batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )
        items = list_redfin_screening_items(db_path=screening_db)

        # Act
        rows = build_screening_report_rows(
            items, db_path=screening_db
        )
        by_id = {r.screening_id: r for r in rows}

        # Assert
        assert by_id[4].saved_for_analysis is True
        assert by_id[4].candidate_has_enrichment is False
        assert by_id[5].saved_for_analysis is False
        assert by_id[5].next_step

    def test_next_step_text_per_status(self, screening_db):
        # Arrange
        batch_mark_screening_items_opened([5], db_path=screening_db)
        items = list_redfin_screening_items(db_path=screening_db)

        # Act
        rows = build_screening_report_rows(
            items, db_path=screening_db
        )
        by_id = {r.screening_id: r for r in rows}

        # Assert
        assert "inspect" in by_id[4].next_step.lower()
        assert "save for analysis" in by_id[5].next_step.lower()


class TestBatchCliCommands:
    """CLI surface for batch actions."""

    @pytest.mark.parametrize("command_name", BATCH_COMMANDS)
    def test_command_registered(self, command_name):
        # Assert
        assert command_name in _command_map()

    @pytest.mark.parametrize("command_name", BATCH_COMMANDS)
    def test_command_uses_canonical_db_default(self, command_name):
        # Act
        default = _db_default(_command_map()[command_name])

        # Assert
        assert default == config.database_path
        assert default == "db/marketsentry.db"

    def test_cli_batch_mark_opened(self, screening_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "batch-mark-screening-items-opened",
                "--screening-ids",
                "4,5,6",
                "--db",
                screening_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        items = list_redfin_screening_items(db_path=screening_db)
        assert all(i.status == "opened" for i in items)

    def test_cli_batch_save(self, screening_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "batch-save-screening-items",
                "--screening-ids",
                "4,5",
                "--notes",
                "Batch save after visual review",
                "--db",
                screening_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Succeeded: 2" in result.output

    def test_cli_batch_reject(self, screening_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "batch-reject-screening-items",
                "--screening-ids",
                "4",
                "--db",
                screening_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Succeeded: 1" in result.output

    def test_cli_batch_hold(self, screening_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "batch-hold-screening-items",
                "--screening-ids",
                "5,6",
                "--db",
                screening_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Succeeded: 2" in result.output

    def test_cli_rejects_empty_id_list(self, screening_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "batch-hold-screening-items",
                "--screening-ids",
                "",
                "--db",
                screening_db,
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "No screening IDs" in result.output

    def test_cli_reports_invalid_ids(self, screening_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "batch-hold-screening-items",
                "--screening-ids",
                "4,abc",
                "--db",
                screening_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "invalid" in result.output.lower()

    def test_cli_screening_next_steps(self, screening_db, tmp_path):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "screening-next-steps",
                "--db",
                screening_db,
                "--project-root",
                str(tmp_path),
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Screening Next Steps" in result.output
        assert "Recommended Steps" in result.output

    def test_cli_accepts_custom_db(self, screening_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "screening-next-steps",
                "--db",
                screening_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "No such option" not in result.output

    def test_single_save_supports_refresh_flag(self):
        # Arrange
        callback = _command_map()["save-screening-item-for-analysis"]

        # Act
        params = inspect.signature(callback).parameters

        # Assert
        assert "refresh" in params

    def test_batch_save_supports_refresh_flag(self):
        # Arrange
        callback = _command_map()["batch-save-screening-items"]

        # Act
        params = inspect.signature(callback).parameters

        # Assert
        assert "refresh" in params
        assert params["refresh"].default.default is False


class TestDashboardBatchSection:
    """Dashboard exposes the batch forms."""

    def test_batch_forms_present(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        for form_key in [
            "screening_batch_save_form",
            "screening_batch_reject_form",
            "screening_batch_hold_form",
            "screening_batch_open_form",
        ]:
            assert form_key in content

    def test_next_steps_panel_present(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "summarize_screening_operator_status" in content
        assert "Next Steps" in content

    def test_refresh_checkbox_present(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "batch_save_refresh" in content

    def test_dashboard_module_imports(self):
        # Act
        import marketsentry.dashboard_app as dash

        # Assert
        assert dash is not None


class TestModelsExposed:
    """Requested models exist and are usable."""

    def test_batch_request_model(self):
        # Act
        request = RedfinScreeningBatchActionRequest(
            screening_ids=[4, 5], action="hold"
        )

        # Assert
        assert request.screening_ids == [4, 5]
        assert request.refresh is False

    def test_batch_result_counts(self):
        # Act
        result = RedfinScreeningBatchActionResult(action="hold")

        # Assert
        assert result.succeeded_count == 0
        assert result.failed_count == 0
        assert result.created_candidate_ids == []

    def test_next_step_model(self):
        # Act
        step = RedfinScreeningNextStep(
            step_id="x", message="do the thing", count=2
        )

        # Assert
        assert step.severity == "info"
        assert step.count == 2


class TestScreeningImportDoesNotCreateCandidates:
    """Imports must never promote to the candidate queue."""

    def test_csv_import_creates_no_candidates(self, tmp_path):
        # Arrange
        from marketsentry.database import init_db
        from marketsentry.redfin_screening_queue import (
            import_redfin_screening_urls,
        )

        db_path = str(tmp_path / "import.db")
        init_db(db_path)
        ensure_redfin_screening_queue_schema(db_path=db_path)

        csv_file = tmp_path / "urls.csv"
        csv_file.write_text(
            "redfin_url,address,city,notes\n"
            "https://www.redfin.com/CA/Temecula/"
            "31801-Valone-Ct-92591/home/6242670,"
            "31801 Valone Ct,Temecula,\n",
            encoding="utf-8",
        )

        # Act
        import_redfin_screening_urls(
            str(csv_file), db_path=db_path
        )

        # Assert
        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_candidates_appear_only_after_explicit_save(
        self, screening_db
    ):
        # Arrange
        conn = sqlite3.connect(screening_db)
        before = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()

        # Act
        batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )

        # Assert
        conn = sqlite3.connect(screening_db)
        after = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert before == 0
        assert after == 1


class TestSafetyInvariants:
    """Milestone 53 adds no unsafe capability."""

    def test_no_network_imports_in_screening_module(self):
        # Arrange
        source = (
            SRC_DIR / "redfin_screening_queue.py"
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
        ]:
            assert banned not in source

    def test_no_outbound_notifications(self):
        # Arrange
        source = (
            SRC_DIR / "redfin_screening_queue.py"
        ).read_text(encoding="utf-8")

        # Assert
        for banned in ["smtp", "send_email", "webhook", "sms"]:
            assert banned not in source.lower()

    def test_no_credentials_requested(self):
        # Arrange
        source = (
            SRC_DIR / "redfin_screening_queue.py"
        ).read_text(encoding="utf-8")

        # Assert
        for banned in ["password", "api_key", "secret"]:
            assert banned not in source.lower()

    def test_no_walkability_fields(self):
        # Arrange
        source = (
            SRC_DIR / "redfin_screening_queue.py"
        ).read_text(encoding="utf-8")

        # Assert
        for banned in [
            "walkability",
            "walk_score",
            "transit_score",
            "bike_score",
        ]:
            assert banned not in source.lower()

    def test_quiet_gatekeeper_threshold_unchanged(self):
        # Assert
        assert config.quiet_score_minimum == 7.0

    def test_quiet_gatekeeper_behavior_unchanged(self):
        # Arrange
        from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper

        # Act
        passing, _ = apply_quiet_gatekeeper(9.9, 1.3)
        failing, _ = apply_quiet_gatekeeper(6.9, 1.1)

        # Assert
        assert passing == "pass"
        assert failing == "fail_noise_risk"

    def test_low_vibrancy_does_not_rescue_poor_quiet(self):
        # Arrange
        from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper

        # Act
        result, _ = apply_quiet_gatekeeper(5.0, 0.1)

        # Assert
        assert result == "fail_noise_risk"

    def test_batch_save_does_not_overwrite_candidate_fields(
        self, screening_db
    ):
        # Arrange: an existing candidate carries enriched values
        from marketsentry.database import insert_candidate
        from marketsentry.models import CandidateProperty

        url = (
            "https://www.redfin.com/CA/Temecula/"
            "31801-Valone-Ct-92591/home/6242670"
        )
        candidate_id = insert_candidate(
            CandidateProperty(
                source_site="redfin",
                source_search_url="",
                redfin_url=url,
                address="31801 Valone Ct",
                city="Temecula",
                beds=4,
                baths=3.0,
                sqft=2500,
                quiet_score=9.1,
                vibrancy_score=1.4,
            ),
            skip_if_exists=True,
            database_path=screening_db,
        )

        # Act
        batch_save_screening_items_for_analysis(
            [4], db_path=screening_db
        )

        # Assert: source-of-truth fields survive the link
        conn = sqlite3.connect(screening_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT beds, baths, sqft, quiet_score, "
            "vibrancy_score FROM candidate_review_queue "
            "WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        conn.close()

        assert row["beds"] == 4
        assert row["baths"] == 3.0
        assert row["sqft"] == 2500
        assert row["quiet_score"] == 9.1
        assert row["vibrancy_score"] == 1.4
