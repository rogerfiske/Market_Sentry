"""Milestone 52A: global database default stabilization tests.

Covers:
- No live code defaults to the legacy data/market_sentry.db path.
- The 9 previously affected CLI commands default to config.database_path.
- Those commands still accept an explicit --db.
- Demo/sample cleanup is dry-run by default and never removes real data.
- Stray artifact detection reports but does not delete without confirm.
- Safety invariants: no live retrieval, browser automation, outbound
  notifications, credential storage, or walkability fields.

All tests are local-only and perform no network calls.
"""

import ast
import inspect
import io
import sqlite3
import tokenize
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from marketsentry.cli import app
from marketsentry.config import config
from marketsentry.demo_data_cleanup import (
    DEMO_MARKER_ADDRESSES,
    PROTECTED_ADDRESSES,
    build_cleanup_plan,
    detect_stray_files,
    execute_cleanup,
    identify_demo_records,
    is_demo_address,
    is_protected_address,
    summarize_cleanup_plan,
)

LEGACY_DB_PATH = "data/market_sentry.db"

AFFECTED_COMMANDS = [
    "persist-portfolio-trend-alerts",
    "compare-portfolio-trend-alert-runs",
    "portfolio-trend-alert-history-summary",
    "export-portfolio-trend-alert-history-report",
    "export-portfolio-trend-alert-run-comparison",
    "portfolio-alert-focus",
    "export-portfolio-alert-focus-digest",
    "portfolio-alert-email-digest",
    "export-portfolio-alert-email-digest",
]

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "marketsentry"

# demo_data_cleanup.py legitimately names the legacy path: cleaning up
# the file that path created is the module's job. It is verified
# separately by TestLegacyPathOnlyReferencedAsArtifact.
LEGACY_PATH_ALLOWED_MODULES = {"demo_data_cleanup.py"}


def _strip_prose(source: str) -> str:
    """Return source with comments and docstrings removed.

    Guardrail modules legitimately mention banned terms in prose while
    documenting that they do not implement them. Scanning raw text
    produces false positives, so compare executable code only.
    """
    without_comments = []
    readline = io.StringIO(source).readline
    for token in tokenize.generate_tokens(readline):
        if token.type == tokenize.COMMENT:
            continue
        without_comments.append(token)
    code = tokenize.untokenize(without_comments)

    tree = ast.parse(code)
    docstrings = set()
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
                docstrings.add(doc)

    for doc in docstrings:
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
    signature = inspect.signature(callback)
    param = signature.parameters["db"]
    default = param.default
    if isinstance(default, typer.models.OptionInfo):
        return default.default
    return default


@pytest.fixture
def seeded_db(tmp_path):
    """Build a database mixing demo records with real user records."""
    db_file = tmp_path / "marketsentry.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE redfin_screening_queue (
            screening_id INTEGER PRIMARY KEY,
            address TEXT,
            candidate_id INTEGER
        );
        CREATE TABLE candidate_review_queue (
            candidate_id INTEGER PRIMARY KEY,
            address TEXT
        );
        CREATE TABLE watched_properties (
            property_id INTEGER PRIMARY KEY,
            address TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO redfin_screening_queue "
        "(screening_id, address, candidate_id) VALUES (?, ?, ?)",
        [
            (1, "40000 Example St", 6),
            (2, "30000 Sample Ave", None),
            (3, "55555 Fixture Ln 92562", None),
            (4, "31801 Valone Ct", None),
            (5, "31457 Britton Cir", None),
            (6, "41451 Royal Dornoch Ct", None),
        ],
    )
    conn.executemany(
        "INSERT INTO candidate_review_queue "
        "(candidate_id, address) VALUES (?, ?)",
        [
            (1, "12345 Sample St"),
            (2, "67890 Busy Ave"),
            (3, "11111 Unknown Rd"),
            (4, "32420 San Marco Dr,Temecula, CA 92592"),
            (5, "32152 Camino Nunez,Temecula, CA 92592"),
            (6, "40000 Example St"),
        ],
    )
    conn.executemany(
        "INSERT INTO watched_properties "
        "(property_id, address) VALUES (?, ?)",
        [
            (1, "12345 Sample St"),
            (2, "32420 San Marco Dr,Temecula, CA 92592"),
        ],
    )
    conn.commit()
    conn.close()
    return str(db_file)


class TestNoLegacyDatabaseDefaults:
    """The legacy wrong default must not appear in live code."""

    def test_no_legacy_path_anywhere_in_source(self):
        # Arrange
        offenders = []

        # Act
        for py_file in SRC_DIR.rglob("*.py"):
            if py_file.name in LEGACY_PATH_ALLOWED_MODULES:
                continue
            text = py_file.read_text(encoding="utf-8")
            if LEGACY_DB_PATH in text:
                offenders.append(str(py_file))

        # Assert
        assert offenders == [], (
            f"Legacy DB path still present in: {offenders}"
        )

    @pytest.mark.parametrize(
        "module_name",
        [
            "cli.py",
            "dashboard_app.py",
            "release_candidate.py",
            "local_operations_bundle.py",
        ],
    )
    def test_named_module_has_no_legacy_default(self, module_name):
        # Arrange
        target = SRC_DIR / module_name

        # Act
        text = target.read_text(encoding="utf-8")

        # Assert
        assert LEGACY_DB_PATH not in text

    def test_no_cli_command_defaults_to_legacy_path(self):
        # Arrange
        commands = _command_map()
        offenders = []

        # Act
        for name, callback in commands.items():
            signature = inspect.signature(callback)
            if "db" not in signature.parameters:
                continue
            if _db_default(callback) == LEGACY_DB_PATH:
                offenders.append(name)

        # Assert
        assert offenders == []


class TestLegacyPathOnlyReferencedAsArtifact:
    """The cleanup module names the legacy path only as a stray file."""

    def test_legacy_path_is_not_assigned_as_a_db_default(self):
        # Arrange
        source = (
            SRC_DIR / "demo_data_cleanup.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        offenders = []

        # Act: flag any assignment binding the legacy path to a
        # database-path-looking name.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not isinstance(node.value, ast.Constant):
                continue
            if node.value.value != LEGACY_DB_PATH:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and "db" in (
                    target.id.lower()
                ):
                    offenders.append(target.id)

        # Assert
        assert offenders == []

    def test_legacy_path_appears_in_stray_artifact_list(self):
        # Arrange
        from marketsentry.demo_data_cleanup import (
            STRAY_FILE_CANDIDATES,
        )

        # Act
        paths = [s["path"] for s in STRAY_FILE_CANDIDATES]

        # Assert
        assert LEGACY_DB_PATH in paths

    def test_legacy_path_is_labelled_as_the_old_wrong_default(self):
        # Arrange
        from marketsentry.demo_data_cleanup import (
            STRAY_FILE_CANDIDATES,
        )

        # Act
        entry = next(
            s
            for s in STRAY_FILE_CANDIDATES
            if s["path"] == LEGACY_DB_PATH
        )

        # Assert
        assert entry["kind"] == "legacy_wrong_default"
        assert "db/marketsentry.db" in entry["explanation"]


class TestAffectedCommandDefaults:
    """The 9 affected commands use the canonical database."""

    @pytest.mark.parametrize("command_name", AFFECTED_COMMANDS)
    def test_command_is_registered(self, command_name):
        # Arrange / Act
        commands = _command_map()

        # Assert
        assert command_name in commands

    @pytest.mark.parametrize("command_name", AFFECTED_COMMANDS)
    def test_command_defaults_to_config_database_path(
        self, command_name
    ):
        # Arrange
        callback = _command_map()[command_name]

        # Act
        default = _db_default(callback)

        # Assert
        assert default == config.database_path
        assert default == "db/marketsentry.db"

    @pytest.mark.parametrize("command_name", AFFECTED_COMMANDS)
    def test_command_still_accepts_explicit_db(
        self, command_name, tmp_path
    ):
        # Arrange
        runner = CliRunner()
        custom_db = tmp_path / "custom.db"
        sqlite3.connect(custom_db).close()

        # Act
        result = runner.invoke(
            app, [command_name, "--db", str(custom_db)]
        )

        # Assert: the option is accepted, not rejected as unknown
        assert "No such option" not in result.output
        assert "Got unexpected extra argument" not in result.output

    def test_running_without_db_does_not_create_legacy_file(
        self, tmp_path, monkeypatch
    ):
        # Arrange
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        runner = CliRunner()
        legacy = tmp_path / "data" / "market_sentry.db"

        # Act
        for command_name in AFFECTED_COMMANDS:
            runner.invoke(app, [command_name])

        # Assert
        assert not legacy.exists()


class TestAddressGuards:
    """Demo detection must never match real user properties."""

    @pytest.mark.parametrize("address", PROTECTED_ADDRESSES)
    def test_protected_addresses_are_never_demo(self, address):
        # Assert
        assert is_protected_address(address) is True
        assert is_demo_address(address) is False

    @pytest.mark.parametrize("address", DEMO_MARKER_ADDRESSES)
    def test_demo_markers_are_detected(self, address):
        # Assert
        assert is_demo_address(address) is True
        assert is_protected_address(address) is False

    def test_address_with_appended_city_state_still_protected(self):
        # Arrange
        address = "32420 San Marco Dr,Temecula, CA 92592"

        # Assert
        assert is_protected_address(address) is True
        assert is_demo_address(address) is False

    def test_none_and_empty_addresses_are_not_demo(self):
        # Assert
        assert is_demo_address(None) is False
        assert is_demo_address("") is False
        assert is_protected_address(None) is False


class TestIdentifyDemoRecords:
    """Identification is read-only and correctly scoped."""

    def test_identifies_all_demo_records(self, seeded_db):
        # Act
        records = identify_demo_records(seeded_db)

        # Assert
        assert len(records) == 8

    def test_excludes_every_real_record(self, seeded_db):
        # Act
        records = identify_demo_records(seeded_db)

        # Assert
        for record in records:
            assert not is_protected_address(record.address)

    def test_identification_does_not_mutate(self, seeded_db):
        # Arrange
        conn = sqlite3.connect(seeded_db)
        before = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()

        # Act
        identify_demo_records(seeded_db)

        # Assert
        conn = sqlite3.connect(seeded_db)
        after = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert before == after

    def test_missing_database_returns_empty(self, tmp_path):
        # Act
        records = identify_demo_records(
            str(tmp_path / "absent.db")
        )

        # Assert
        assert records == []


class TestCleanupPlan:
    """Plan building never mutates state."""

    def test_plan_reports_counts(self, seeded_db, tmp_path):
        # Act
        plan = build_cleanup_plan(seeded_db, str(tmp_path))

        # Assert
        assert plan.demo_record_count == 8
        assert plan.protected_records_found == 6

    def test_summary_groups_by_category(self, seeded_db, tmp_path):
        # Act
        plan = build_cleanup_plan(seeded_db, str(tmp_path))
        summary = summarize_cleanup_plan(plan)

        # Assert
        assert summary["by_category"]["seeded_sample"] == 4
        assert summary["by_category"]["screening_demo"] == 4


class TestExecuteCleanup:
    """Mutation requires explicit confirmation."""

    def test_dry_run_is_default_and_removes_nothing(
        self, seeded_db, tmp_path
    ):
        # Arrange
        plan = build_cleanup_plan(seeded_db, str(tmp_path))

        # Act
        result = execute_cleanup(plan)

        # Assert
        assert result.dry_run is True
        assert result.removed_record_count == 0
        conn = sqlite3.connect(seeded_db)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert remaining == 6

    def test_confirm_removes_only_demo_records(
        self, seeded_db, tmp_path
    ):
        # Arrange
        plan = build_cleanup_plan(seeded_db, str(tmp_path))

        # Act
        result = execute_cleanup(plan, confirm=True)

        # Assert
        assert result.dry_run is False
        assert result.removed_record_count == 8

        conn = sqlite3.connect(seeded_db)
        candidates = [
            r[0]
            for r in conn.execute(
                "SELECT address FROM candidate_review_queue"
            )
        ]
        screening = [
            r[0]
            for r in conn.execute(
                "SELECT address FROM redfin_screening_queue"
            )
        ]
        watched = [
            r[0]
            for r in conn.execute(
                "SELECT address FROM watched_properties"
            )
        ]
        conn.close()

        assert len(candidates) == 2
        assert len(screening) == 3
        assert len(watched) == 1
        for address in candidates + screening + watched:
            assert is_protected_address(address)

    def test_real_user_addresses_survive_confirm(
        self, seeded_db, tmp_path
    ):
        # Arrange
        plan = build_cleanup_plan(seeded_db, str(tmp_path))

        # Act
        execute_cleanup(plan, confirm=True)

        # Assert
        conn = sqlite3.connect(seeded_db)
        rows = [
            r[0]
            for r in conn.execute(
                "SELECT address FROM redfin_screening_queue"
            )
        ]
        conn.close()
        assert "31801 Valone Ct" in rows
        assert "31457 Britton Cir" in rows
        assert "41451 Royal Dornoch Ct" in rows

    def test_protected_record_in_plan_is_skipped(
        self, seeded_db, tmp_path
    ):
        # Arrange: force a protected record into the plan to prove the
        # second guard rejects it independently of plan construction.
        plan = build_cleanup_plan(seeded_db, str(tmp_path))
        smuggled = plan.demo_records[0].model_copy(
            update={
                "address": "32420 San Marco Dr",
                "record_id": 4,
                "table_name": "candidate_review_queue",
            }
        )
        plan.demo_records.append(smuggled)

        # Act
        result = execute_cleanup(plan, confirm=True)

        # Assert
        assert len(result.skipped_protected) == 1
        conn = sqlite3.connect(seeded_db)
        survivors = [
            r[0]
            for r in conn.execute(
                "SELECT address FROM candidate_review_queue"
            )
        ]
        conn.close()
        assert any("San Marco" in a for a in survivors)


class TestStrayFileHandling:
    """Stray files are reported but never deleted implicitly."""

    def test_detects_present_stray_files(self, tmp_path):
        # Arrange
        (tmp_path / "dbmarketsentry.db").write_text("")
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "market_sentry.db").write_text("")

        # Act
        artifacts = detect_stray_files(str(tmp_path))
        present = [a.path for a in artifacts if a.exists]

        # Assert
        assert "dbmarketsentry.db" in present
        assert "data/market_sentry.db" in present

    def test_absent_stray_files_reported_as_missing(self, tmp_path):
        # Act
        artifacts = detect_stray_files(str(tmp_path))

        # Assert
        assert all(a.exists is False for a in artifacts)

    def test_confirm_alone_does_not_delete_stray_files(
        self, seeded_db, tmp_path
    ):
        # Arrange
        stray = tmp_path / "dbmarketsentry.db"
        stray.write_text("")
        plan = build_cleanup_plan(seeded_db, str(tmp_path))

        # Act
        execute_cleanup(plan, confirm=True)

        # Assert
        assert stray.exists()

    def test_stray_flag_deletes_only_stray_files(
        self, seeded_db, tmp_path
    ):
        # Arrange
        stray = tmp_path / "dbmarketsentry.db"
        stray.write_text("")
        keeper = tmp_path / "keepme.txt"
        keeper.write_text("real")
        plan = build_cleanup_plan(seeded_db, str(tmp_path))

        # Act
        result = execute_cleanup(
            plan, confirm=True, confirm_stray_files=True
        )

        # Assert
        assert not stray.exists()
        assert keeper.exists()
        assert "dbmarketsentry.db" in result.removed_files


class TestCleanupCliCommand:
    """CLI surface is dry-run by default."""

    def test_command_is_registered(self):
        # Assert
        assert "cleanup-demo-data" in _command_map()

    def test_cli_dry_run_by_default(self, seeded_db, tmp_path):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "cleanup-demo-data",
                "--db",
                seeded_db,
                "--project-root",
                str(tmp_path),
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        conn = sqlite3.connect(seeded_db)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert remaining == 6

    def test_cli_dry_run_flag_overrides_confirm(
        self, seeded_db, tmp_path
    ):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "cleanup-demo-data",
                "--db",
                seeded_db,
                "--project-root",
                str(tmp_path),
                "--confirm",
                "--dry-run",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        conn = sqlite3.connect(seeded_db)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert remaining == 6

    def test_cli_confirm_applies_changes(self, seeded_db, tmp_path):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "cleanup-demo-data",
                "--db",
                seeded_db,
                "--project-root",
                str(tmp_path),
                "--confirm",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "DRY RUN" not in result.output
        conn = sqlite3.connect(seeded_db)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        conn.close()
        assert remaining == 2


class TestSafetyInvariants:
    """Milestone 52A adds no unsafe capability."""

    def test_cleanup_module_has_no_network_imports(self):
        # Arrange
        source = _strip_prose(
            (SRC_DIR / "demo_data_cleanup.py").read_text(
                encoding="utf-8"
            )
        )

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

    def test_cleanup_module_adds_no_walkability_fields(self):
        # Arrange
        source = _strip_prose(
            (SRC_DIR / "demo_data_cleanup.py").read_text(
                encoding="utf-8"
            )
        )

        # Assert
        for banned in [
            "walk_score",
            "walkability",
            "transit_score",
            "bike_score",
        ]:
            assert banned not in source

    def test_cleanup_module_stores_no_credentials(self):
        # Arrange
        source = _strip_prose(
            (SRC_DIR / "demo_data_cleanup.py").read_text(
                encoding="utf-8"
            )
        )

        # Assert
        for banned in ["password", "api_key", "token", "secret"]:
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
