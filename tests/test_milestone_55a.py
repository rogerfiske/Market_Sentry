"""Milestone 55A: workflow, test isolation, and coverage stabilization.

Covers three stabilization fixes:

1. run_operator_refresh_workflow propagates a custom exports_dir to
   every report step.
2. Release document generation can be directed away from the tracked
   docs/ directory, so the test suite no longer dirties it.
3. A coverage floor is configured and documented.

All tests are local-only and perform no network calls.
"""

import ast
import inspect
import io
import sqlite3
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest
import tomllib

from marketsentry.candidate_report import (
    export_candidate_analysis_report,
)
from marketsentry.cli import app
from marketsentry.config import config
from marketsentry.monitoring_report import (
    export_watchlist_monitoring_report,
)
from marketsentry.operator_workflow import (
    run_operator_refresh_workflow,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src" / "marketsentry"

TRACKED_RELEASE_DOCS = [
    "docs/RELEASE_CANDIDATE_CHECKLIST.md",
    "docs/RELEASE_NOTES_DRAFT.md",
    "docs/RELEASE_NOTES_FINAL.md",
]


def _strip_prose(source: str) -> str:
    """Return source with comments and docstrings removed.

    These modules state in prose that they add no walkability fields
    and store no credentials. Scanning raw text flags the guarantee
    itself, so compare executable code only.
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


def _module_code(module_name: str) -> str:
    """Load a source module with prose stripped."""
    return _strip_prose(
        (SRC_DIR / module_name).read_text(encoding="utf-8")
    )


def _command_map():
    """Map CLI command name to its callback."""
    mapping = {}
    for command in app.registered_commands:
        name = command.name or command.callback.__name__.replace(
            "_", "-"
        )
        mapping[name] = command.callback
    return mapping


@pytest.fixture
def workflow_db(tmp_path):
    """Database with one scored candidate and one watched property."""
    db_path = str(tmp_path / "workflow.db")
    from marketsentry.database import init_db

    init_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO candidate_review_queue "
        "(candidate_id, discovery_date, source_site, "
        "source_search_url, redfin_url, address, "
        "normalized_address, city, zip, quiet_score, "
        "vibrancy_score, quiet_gatekeeper_result, review_status, "
        "user_decision) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            4, "2026-08-01", "redfin", "",
            "https://www.redfin.com/CA/Temecula/"
            "32420-San-Marco-Dr-92592/home/6244468",
            "32420 San Marco Dr", "32420 san marco dr",
            "Temecula", "92592", 9.9, 1.3, "pass", "reviewed",
            "save",
        ),
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


class TestExportsDirPropagation:
    """Every refresh report step honors a custom exports_dir."""

    def test_refresh_writes_into_custom_dir(
        self, workflow_db, tmp_path
    ):
        # Arrange
        exports = tmp_path / "custom_exports"

        # Act
        run_operator_refresh_workflow(
            db_path=workflow_db, exports_dir=str(exports)
        )

        # Assert
        assert exports.is_dir()
        assert list(exports.iterdir())

    def test_candidate_analysis_lands_in_custom_dir(
        self, workflow_db, tmp_path
    ):
        # Arrange
        exports = tmp_path / "custom_exports"

        # Act
        run_operator_refresh_workflow(
            db_path=workflow_db, exports_dir=str(exports)
        )

        # Assert
        assert list(exports.glob("candidate_analysis_*.csv"))

    def test_monitoring_report_lands_in_custom_dir(
        self, workflow_db, tmp_path
    ):
        # Arrange
        exports = tmp_path / "custom_exports"

        # Act
        run_operator_refresh_workflow(
            db_path=workflow_db, exports_dir=str(exports)
        )

        # Assert
        assert list(exports.glob("watchlist_monitoring_*.csv"))

    def test_operations_digest_lands_in_custom_dir(
        self, workflow_db, tmp_path
    ):
        # This one regressed because the exporter separates its scan
        # directory from its write directory.
        # Arrange
        exports = tmp_path / "custom_exports"

        # Act
        run_operator_refresh_workflow(
            db_path=workflow_db, exports_dir=str(exports)
        )

        # Assert
        assert list(exports.glob("operations_digest_*"))

    def test_portfolio_review_pack_lands_in_custom_dir(
        self, workflow_db, tmp_path
    ):
        # Arrange
        exports = tmp_path / "custom_exports"

        # Act
        run_operator_refresh_workflow(
            db_path=workflow_db, exports_dir=str(exports)
        )

        # Assert
        assert list(exports.glob("portfolio_review_pack_*"))

    def test_local_operations_bundle_lands_in_custom_dir(
        self, workflow_db, tmp_path
    ):
        # Arrange
        exports = tmp_path / "custom_exports"

        # Act
        run_operator_refresh_workflow(
            db_path=workflow_db, exports_dir=str(exports)
        )

        # Assert
        assert list(exports.glob("local_operations_bundle_*"))

    def test_nothing_leaks_to_default_exports_dir(
        self, workflow_db, tmp_path
    ):
        # The regression that motivated this milestone: some steps
        # wrote to data/exports regardless of exports_dir.
        # Arrange
        default_dir = Path(config.data_exports_dir)
        default_dir.mkdir(parents=True, exist_ok=True)
        before = set(default_dir.iterdir())
        exports = tmp_path / "custom_exports"

        # Act
        run_operator_refresh_workflow(
            db_path=workflow_db, exports_dir=str(exports)
        )

        # Assert
        after = set(default_dir.iterdir())
        assert after == before

    def test_reported_paths_point_into_custom_dir(
        self, workflow_db, tmp_path
    ):
        # Arrange
        exports = tmp_path / "custom_exports"

        # Act
        result = run_operator_refresh_workflow(
            db_path=workflow_db, exports_dir=str(exports)
        )

        # Assert
        assert result.output_paths
        resolved_exports = exports.resolve()
        for path in result.output_paths:
            assert (
                Path(path).resolve().parent == resolved_exports
            ), f"{path} did not land in the custom directory"

    def test_default_behavior_unchanged_when_not_supplied(
        self, workflow_db
    ):
        # Backward compatibility: omitting exports_dir must still
        # target the configured default.
        # Arrange
        signature = inspect.signature(
            run_operator_refresh_workflow
        )

        # Assert
        assert (
            signature.parameters["exports_dir"].default is None
        )


class TestExporterParameters:
    """The two exporters accept a directory, backward compatibly."""

    def test_candidate_report_accepts_exports_dir(
        self, workflow_db, tmp_path
    ):
        # Act
        path = export_candidate_analysis_report(
            database_path=workflow_db,
            exports_dir=str(tmp_path),
        )

        # Assert
        assert Path(path).parent.resolve() == tmp_path.resolve()

    def test_monitoring_report_accepts_exports_dir(
        self, workflow_db, tmp_path
    ):
        # Act
        export_watchlist_monitoring_report(
            database_path=workflow_db,
            exports_dir=str(tmp_path),
        )

        # Assert
        assert list(tmp_path.glob("watchlist_monitoring_*.csv"))

    def test_output_path_still_wins_over_exports_dir(
        self, workflow_db, tmp_path
    ):
        # output_path names the exact destination, so it must take
        # precedence over the directory hint.
        # Arrange
        explicit = tmp_path / "explicit_name.csv"
        other_dir = tmp_path / "ignored"
        other_dir.mkdir()

        # Act
        path = export_candidate_analysis_report(
            database_path=workflow_db,
            output_path=str(explicit),
            exports_dir=str(other_dir),
        )

        # Assert
        assert Path(path).resolve() == explicit.resolve()
        assert not list(other_dir.iterdir())

    def test_exports_dir_is_optional_on_both(self):
        # Backward compatibility for existing callers.
        # Assert
        for func in (
            export_candidate_analysis_report,
            export_watchlist_monitoring_report,
        ):
            param = inspect.signature(func).parameters[
                "exports_dir"
            ]
            assert param.default is None

    def test_candidate_report_uses_config_not_hardcoded_path(self):
        # It previously hardcoded "data/exports", ignoring config.
        # Arrange
        source = (
            SRC_DIR / "candidate_report.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert 'Path("data/exports")' not in source
        assert "config.data_exports_dir" in source


class TestReleaseDocIsolation:
    """Release generation can be directed away from tracked docs."""

    def test_candidate_report_cli_exposes_project_root(self):
        # Arrange
        callback = _command_map()[
            "export-release-candidate-report"
        ]

        # Act
        params = inspect.signature(callback).parameters

        # Assert
        assert "project_root" in params

    def test_finalization_cli_exposes_project_root(self):
        # Arrange
        callback = _command_map()[
            "export-release-finalization-report"
        ]

        # Act
        params = inspect.signature(callback).parameters

        # Assert
        assert "project_root" in params

    def test_project_root_defaults_to_current_dir(self):
        # Backward compatibility for real operator use.
        # Arrange
        callback = _command_map()[
            "export-release-candidate-report"
        ]

        # Act
        default = inspect.signature(callback).parameters[
            "project_root"
        ].default

        # Assert
        assert default.default == "."

    def test_checklist_writes_into_supplied_root(self, tmp_path):
        # Arrange
        from marketsentry.release_candidate import (
            build_release_candidate_report,
            export_release_candidate_report,
        )

        result = build_release_candidate_report()

        # Act
        export_release_candidate_report(
            result,
            output_dir=str(tmp_path),
            fmt="md",
            project_root=str(tmp_path),
        )

        # Assert
        assert (
            tmp_path / "docs" / "RELEASE_CANDIDATE_CHECKLIST.md"
        ).is_file()
        assert (
            tmp_path / "docs" / "RELEASE_NOTES_DRAFT.md"
        ).is_file()

    def test_final_notes_write_into_supplied_root(self, tmp_path):
        # Arrange
        from marketsentry.release_finalization import (
            build_release_finalization_report,
            export_release_finalization_report,
        )

        result = build_release_finalization_report()

        # Act
        export_release_finalization_report(
            result,
            output_dir=str(tmp_path),
            fmt="md",
            project_root=str(tmp_path),
        )

        # Assert
        assert (
            tmp_path / "docs" / "RELEASE_NOTES_FINAL.md"
        ).is_file()

    def test_release_generation_still_works(self, tmp_path):
        # The fix must not disable the real feature.
        # Arrange
        from marketsentry.release_candidate import (
            build_release_candidate_report,
            export_release_candidate_report,
        )

        result = build_release_candidate_report()

        # Act
        exported = export_release_candidate_report(
            result,
            output_dir=str(tmp_path),
            fmt="both",
            project_root=str(tmp_path),
        )

        # Assert
        assert exported.report.output_paths
        checklist = (
            tmp_path / "docs" / "RELEASE_CANDIDATE_CHECKLIST.md"
        )
        assert "Release Candidate Checklist" in (
            checklist.read_text(encoding="utf-8")
        )

    def test_tracked_release_docs_exist_in_repo(self):
        # The real docs must not have been deleted by the fix.
        # Assert
        for relative in TRACKED_RELEASE_DOCS:
            assert (REPO_ROOT / relative).is_file()

    @pytest.mark.skipif(
        not (REPO_ROOT / ".git").exists(),
        reason="not a git checkout",
    )
    def test_tracked_release_docs_are_not_dirty(self):
        # Guards the isolation fix: if a future test regenerates a
        # tracked release doc, this fails and names the file.
        # Act
        completed = subprocess.run(
            [
                "git", "status", "--porcelain", "--",
                *TRACKED_RELEASE_DOCS,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        # Assert
        if completed.returncode != 0:
            pytest.skip("git unavailable")
        assert completed.stdout.strip() == "", (
            "Tracked release docs were modified by the test run: "
            f"{completed.stdout.strip()}"
        )


class TestCoveragePolicy:
    """A coverage floor is configured and documented."""

    def test_fail_under_is_configured(self):
        # Arrange
        with open(
            REPO_ROOT / "pyproject.toml", "rb"
        ) as handle:
            data = tomllib.load(handle)

        # Act
        report = data["tool"]["coverage"]["report"]

        # Assert
        assert "fail_under" in report
        assert isinstance(report["fail_under"], int)

    def test_floor_is_conservative_but_meaningful(self):
        # A floor at 0 would be theatre; one above the measured value
        # would flap.
        # Arrange
        with open(
            REPO_ROOT / "pyproject.toml", "rb"
        ) as handle:
            data = tomllib.load(handle)

        # Act
        floor = data["tool"]["coverage"]["report"]["fail_under"]

        # Assert
        assert 70 <= floor <= 76

    def test_policy_is_documented(self):
        # Arrange
        adr = (
            REPO_ROOT
            / "docs"
            / "decisions"
            / "055-workflow-test-coverage-stabilization.md"
        )

        # Assert
        assert adr.is_file()
        text = adr.read_text(encoding="utf-8").lower()
        assert "fail_under" in text
        assert "80" in text

    def test_policy_forbids_network_tests_for_coverage(self):
        # Arrange
        pyproject = (
            REPO_ROOT / "pyproject.toml"
        ).read_text(encoding="utf-8")

        # Assert
        assert "real network" in pyproject.lower()


class TestSafetyInvariants:
    """Stabilization adds no capability and changes no domain rule."""

    def test_no_new_network_imports_in_touched_modules(self):
        # Assert
        for module in (
            "operator_workflow.py",
            "candidate_report.py",
            "monitoring_report.py",
        ):
            source = _module_code(module)
            for banned in [
                "import requests",
                "import httpx",
                "playwright",
                "selenium",
                "webbrowser",
            ]:
                assert banned not in source

    def test_no_outbound_notifications_in_touched_modules(self):
        # Assert
        for module in (
            "operator_workflow.py",
            "candidate_report.py",
            "monitoring_report.py",
        ):
            source = _module_code(module).lower()
            for banned in ["smtp", "send_email", "webhook"]:
                assert banned not in source

    def test_no_credentials_in_touched_modules(self):
        # Assert
        for module in (
            "operator_workflow.py",
            "candidate_report.py",
            "monitoring_report.py",
        ):
            source = _module_code(module).lower()
            for banned in ["password", "api_key", "secret"]:
                assert banned not in source

    def test_no_walkability_in_touched_modules(self):
        # Assert
        for module in (
            "operator_workflow.py",
            "candidate_report.py",
            "monitoring_report.py",
        ):
            source = _module_code(module).lower()
            for banned in [
                "walk_score",
                "walkability",
                "transit_score",
                "bike_score",
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

    def test_refresh_does_not_change_redfin_fields(
        self, workflow_db, tmp_path
    ):
        # Arrange
        conn = sqlite3.connect(workflow_db)
        before = conn.execute(
            "SELECT quiet_score, vibrancy_score, "
            "quiet_gatekeeper_result FROM candidate_review_queue "
            "ORDER BY candidate_id"
        ).fetchall()
        conn.close()

        # Act
        run_operator_refresh_workflow(
            db_path=workflow_db,
            exports_dir=str(tmp_path / "exports"),
        )

        # Assert
        conn = sqlite3.connect(workflow_db)
        after = conn.execute(
            "SELECT quiet_score, vibrancy_score, "
            "quiet_gatekeeper_result FROM candidate_review_queue "
            "ORDER BY candidate_id"
        ).fetchall()
        conn.close()
        assert before == after

    def test_no_real_network_calls_available(self):
        # The workflow module must not import a live HTTP client.
        # Arrange
        source = (
            SRC_DIR / "operator_workflow.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "urllib.request" not in source
        assert "StandardLibraryHttpClient" not in source

    def test_python_version_supported(self):
        # tomllib requires 3.11+, which the project already targets.
        # Assert
        assert sys.version_info >= (3, 11)
