"""Milestone 55: HowLoud noise enrichment adapter.

Covers configuration and secret handling, schema, request building,
mocked fetch paths, comparison categories, reports, CLI surface, and
the standing safety invariants.

Every network interaction is mocked with FakeHttpClient. No test
performs a real network call. A sentinel dummy key is used throughout;
it is not a real credential.
"""

import ast
import inspect
import io
import json
import sqlite3
import tokenize
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from marketsentry.cli import app
from marketsentry.config import (
    HOWLOUD_API_KEY_ENV_VAR,
    config,
    get_howloud_api_key,
    mask_secret,
)
from marketsentry.howloud_adapter import (
    AGREEMENT_CLEAR,
    API_KEY_HEADER,
    MANUAL_REVIEW_NEEDED,
    MISSING_HOWLOUD_SCORE,
    MISSING_REDFIN_SCORE,
    POSSIBLE_DISAGREEMENT,
    PROVIDER_NAME,
    HowLoudObservation,
    build_howloud_request_for_candidate,
    compare_howloud_to_redfin,
    ensure_howloud_schema,
    enrich_candidate_with_howloud,
    export_howloud_noise_report,
    fetch_howloud_noise,
    get_howloud_config_status,
    get_latest_howloud_observation,
    howloud_table_exists,
    list_candidates_needing_howloud,
    parse_howloud_response,
    save_howloud_observation,
)
from marketsentry.source_adapters.http_client import FakeHttpClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "marketsentry"


def _strip_prose(source: str) -> str:
    """Return source with comments and docstrings removed.

    This module documents in prose that it does not add walkability
    fields or store credentials. Scanning raw text for those words
    flags the guarantee itself, so compare executable code only.
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


def _hardcoded_secret_assignments(source: str) -> list:
    """Find string literals assigned to secret-looking names.

    The real risk is a key baked into source, not the existence of a
    local variable named api_key.
    """
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, str):
            continue
        if not node.value.value.strip():
            continue
        for target in node.targets:
            name = getattr(target, "id", "").lower()
            if not any(
                marker in name
                for marker in ("key", "secret", "token", "password")
            ):
                continue
            # Constants that name a header or environment variable
            # hold an identifier, not a credential.
            if name.endswith(
                ("_header", "_env_var", "_name", "_var", "_field")
            ):
                continue
            offenders.append(name)
    return offenders

# Obvious non-credential used only to prove masking and redaction.
DUMMY_API_KEY = "dummy-not-a-real-key-WXYZ9999"

HOWLOUD_COMMANDS = [
    "howloud-config-status",
    "list-candidates-needing-howloud",
    "enrich-candidate-howloud",
    "compare-howloud-redfin",
    "export-howloud-noise-report",
]

QUIET_RESPONSE = json.dumps({
    "status": "OK",
    "request": {"lat": 33.4936, "lng": -117.1484},
    "result": {
        "score": 92,
        "scoretext": "Calm",
        "traffic": 4,
        "traffictext": "Calm",
        "airports": 0,
        "airportstext": "Calm",
        "local": 2,
        "localtext": "Calm",
    },
})

LOUD_RESPONSE = json.dumps({
    "status": "OK",
    "request": {"lat": 33.49, "lng": -117.14},
    "result": {
        "score": 62,
        "scoretext": "Busy",
        "traffic": 48,
        "traffictext": "Busy",
        "airports": 2,
        "airportstext": "Active",
        "local": 20,
        "localtext": "Active",
    },
})

# The provider's own Python sample indexes result[0], so the list form
# must parse too.
LIST_SHAPED_RESPONSE = json.dumps({
    "status": "OK",
    "result": [{
        "score": 88,
        "scoretext": "Calm",
        "traffic": 10,
        "traffictext": "Calm",
        "airports": 0,
        "airportstext": "Calm",
        "local": 5,
        "localtext": "Calm",
    }],
})


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
def howloud_env(monkeypatch):
    """Enable HowLoud with a dummy key for the duration of a test."""
    monkeypatch.setenv(HOWLOUD_API_KEY_ENV_VAR, DUMMY_API_KEY)
    monkeypatch.setattr(config, "howloud_enabled", True)
    return DUMMY_API_KEY


@pytest.fixture
def no_howloud_env(monkeypatch):
    """Ensure no key is configured."""
    monkeypatch.delenv(HOWLOUD_API_KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(config, "howloud_enabled", False)


@pytest.fixture
def candidate_db(tmp_path):
    """Database with a passing and a failing candidate."""
    db_path = str(tmp_path / "howloud.db")
    from marketsentry.database import init_db

    init_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO candidate_review_queue "
        "(candidate_id, discovery_date, source_site, "
        "source_search_url, redfin_url, address, "
        "normalized_address, city, zip, quiet_score, "
        "vibrancy_score, quiet_gatekeeper_result, review_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                4, "2026-08-01", "redfin", "",
                "https://www.redfin.com/CA/Temecula/"
                "32420-San-Marco-Dr-92592/home/6244468",
                "32420 San Marco Dr", "32420 san marco dr",
                "Temecula", "92592", 9.9, 1.3, "pass", "reviewed",
            ),
            (
                5, "2026-08-01", "redfin", "",
                "https://www.redfin.com/CA/Temecula/"
                "32152-Camino-Nunez-92592/home/6230280",
                "32152 Camino Nunez", "32152 camino nunez",
                "Temecula", "92592", 6.9, 1.1, "fail_noise_risk",
                "reviewed",
            ),
            (
                8, "2026-08-01", "redfin", "",
                "https://www.redfin.com/CA/Temecula/"
                "31801-Valone-Ct-92591/home/6242670",
                "31801 Valone Ct", "31801 valone ct",
                "Temecula", "92591", None, None, None, "pending",
            ),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


def _save_observation(db_path, candidate_id, response_text):
    """Store a mocked observation for a candidate."""
    request = build_howloud_request_for_candidate(
        candidate_id, latitude=33.4, longitude=-117.1,
        db_path=db_path,
    )
    client = FakeHttpClient(
        response_text=response_text,
        response_content_type="application/json",
    )
    observation = fetch_howloud_noise(
        request, http_client=client, allow_network=True
    )
    save_howloud_observation(observation, db_path=db_path)
    return observation


class TestSecretHandling:
    """The API key must never leak."""

    def test_key_is_not_a_config_model_field(self):
        # A secret stored as a field would surface in reprs and logs.
        # Assert
        fields = type(config).model_fields
        assert "howloud_api_key" not in fields
        assert "api_key" not in " ".join(fields)

    def test_config_repr_never_contains_key(self, howloud_env):
        # Act
        rendered = f"{config!r} {config.model_dump()}"

        # Assert
        assert DUMMY_API_KEY not in rendered

    def test_get_key_reads_environment(self, howloud_env):
        # Assert
        assert get_howloud_api_key() == DUMMY_API_KEY

    def test_get_key_returns_none_when_absent(self, no_howloud_env):
        # Assert
        assert get_howloud_api_key() is None

    def test_mask_shows_only_last_four(self):
        # Act
        masked = mask_secret(DUMMY_API_KEY)

        # Assert
        assert masked.endswith("9999")
        assert DUMMY_API_KEY not in masked
        assert masked.startswith("*")

    def test_mask_fully_hides_short_secrets(self):
        # A short key would be mostly revealed by a suffix.
        # Assert
        assert mask_secret("abc123") == "*" * 8
        assert mask_secret("12345678") == "*" * 8

    def test_mask_handles_absent_secret(self):
        # Assert
        assert mask_secret(None) == "not set"
        assert mask_secret("") == "not set"

    def test_config_status_never_carries_raw_key(
        self, howloud_env
    ):
        # Act
        status = get_howloud_config_status()
        rendered = json.dumps(status.model_dump())

        # Assert
        assert status.api_key_present is True
        assert DUMMY_API_KEY not in rendered

    def test_no_key_literal_in_source(self):
        # Arrange
        source = (
            SRC_DIR / "howloud_adapter.py"
        ).read_text(encoding="utf-8")

        # Assert: no secret baked into the module
        assert DUMMY_API_KEY not in source
        assert _hardcoded_secret_assignments(source) == []

    def test_config_module_has_no_hardcoded_secret(self):
        # Arrange
        source = (
            SRC_DIR / "config.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert _hardcoded_secret_assignments(source) == []


class TestConfigStatus:
    """Config status reporting."""

    def test_status_with_no_key(self, no_howloud_env):
        # Act
        status = get_howloud_config_status()

        # Assert
        assert status.api_key_present is False
        assert status.api_key_masked == "not set"
        assert status.ready is False
        assert any("No API key" in m for m in status.messages)

    def test_status_with_key_present_but_masked(self, howloud_env):
        # Act
        status = get_howloud_config_status()

        # Assert
        assert status.api_key_present is True
        assert status.api_key_masked.endswith("9999")
        assert status.ready is True

    def test_status_key_present_but_disabled(
        self, monkeypatch
    ):
        # Arrange
        monkeypatch.setenv(HOWLOUD_API_KEY_ENV_VAR, DUMMY_API_KEY)
        monkeypatch.setattr(config, "howloud_enabled", False)

        # Act
        status = get_howloud_config_status()

        # Assert
        assert status.api_key_present is True
        assert status.ready is False


class TestSchema:
    """Observation table."""

    def test_schema_creation_is_idempotent(self, tmp_path):
        # Arrange
        db_path = str(tmp_path / "schema.db")

        # Act
        ensure_howloud_schema(db_path)
        ensure_howloud_schema(db_path)
        ensure_howloud_schema(db_path)

        # Assert
        assert howloud_table_exists(db_path) is True

    def test_table_absent_before_creation(self, tmp_path):
        # Arrange
        db_path = str(tmp_path / "absent.db")
        sqlite3.connect(db_path).close()

        # Assert
        assert howloud_table_exists(db_path) is False

    def test_howloud_columns_are_separate_from_redfin(
        self, candidate_db
    ):
        # Arrange
        ensure_howloud_schema(candidate_db)
        conn = sqlite3.connect(candidate_db)

        # Act
        howloud_cols = {
            r[1]
            for r in conn.execute(
                "PRAGMA table_info(howloud_observations)"
            )
        }
        candidate_cols = {
            r[1]
            for r in conn.execute(
                "PRAGMA table_info(candidate_review_queue)"
            )
        }
        conn.close()

        # Assert: HowLoud values live only in their own table
        assert "noise_score" in howloud_cols
        assert "noise_score" not in candidate_cols
        assert "howloud_noise_score" not in candidate_cols


class TestRequestBuilding:
    """Request preparation is offline and read-only."""

    def test_builds_request_with_coordinates(self, candidate_db):
        # Act
        request = build_howloud_request_for_candidate(
            5, latitude=33.4936, longitude=-117.1484,
            db_path=candidate_db,
        )

        # Assert
        assert request.is_ready is True
        assert "lat=33.4936" in request.endpoint_url
        assert "lng=-117.1484" in request.endpoint_url
        assert request.address == "32152 Camino Nunez"

    def test_missing_coordinates_block_request(self, candidate_db):
        # Act
        request = build_howloud_request_for_candidate(
            5, db_path=candidate_db
        )

        # Assert
        assert request.is_ready is False
        assert any(
            "Latitude and longitude are required" in r
            for r in request.blocking_reasons
        )

    def test_out_of_range_coordinates_rejected(self, candidate_db):
        # Act
        request = build_howloud_request_for_candidate(
            5, latitude=200.0, longitude=-500.0,
            db_path=candidate_db,
        )

        # Assert
        assert request.is_ready is False
        assert len(request.blocking_reasons) == 2

    def test_missing_candidate_blocks_request(self, candidate_db):
        # Act
        request = build_howloud_request_for_candidate(
            999, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )

        # Assert
        assert request.is_ready is False
        assert any(
            "not found" in r for r in request.blocking_reasons
        )

    def test_reuses_coordinates_from_prior_observation(
        self, candidate_db
    ):
        # Arrange
        _save_observation(candidate_db, 5, QUIET_RESPONSE)

        # Act: no coordinates supplied this time
        request = build_howloud_request_for_candidate(
            5, db_path=candidate_db
        )

        # Assert
        assert request.is_ready is True
        assert request.latitude == 33.4

    def test_building_request_creates_no_table(self, candidate_db):
        # Act
        build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )

        # Assert
        assert howloud_table_exists(candidate_db) is False


class TestResponseParsing:
    """Parsing tolerates both documented and observed shapes."""

    def test_parses_object_result(self):
        # Act
        parsed = parse_howloud_response(QUIET_RESPONSE)

        # Assert
        assert parsed["noise_score"] == 92.0
        assert parsed["raw_score_label"] == "Calm"
        assert parsed["traffic_score"] == 4.0
        assert parsed["parse_error"] is None

    def test_parses_list_result(self):
        # The provider's own sample uses result[0].
        # Act
        parsed = parse_howloud_response(LIST_SHAPED_RESPONSE)

        # Assert
        assert parsed["noise_score"] == 88.0
        assert parsed["parse_error"] is None

    def test_invalid_json_reports_parse_error(self):
        # Act
        parsed = parse_howloud_response("not json at all")

        # Assert
        assert parsed["parse_error"]
        assert parsed["noise_score"] is None

    def test_missing_result_block_reports_parse_error(self):
        # Act
        parsed = parse_howloud_response(
            json.dumps({"status": "OK"})
        )

        # Assert
        assert parsed["parse_error"]

    def test_empty_list_result_reports_parse_error(self):
        # Act
        parsed = parse_howloud_response(
            json.dumps({"status": "OK", "result": []})
        )

        # Assert
        assert parsed["parse_error"]


class TestFetchBehavior:
    """Network behavior is opt-in and mocked."""

    def test_no_call_without_allow_network(
        self, candidate_db, howloud_env
    ):
        # Arrange
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(response_text=QUIET_RESPONSE)

        # Act
        observation = fetch_howloud_noise(
            request, http_client=client, allow_network=False
        )

        # Assert
        assert client.requests == []
        assert observation.status == "dry_run"

    def test_missing_key_prevents_call(
        self, candidate_db, monkeypatch
    ):
        # Arrange
        monkeypatch.delenv(HOWLOUD_API_KEY_ENV_VAR, raising=False)
        monkeypatch.setattr(config, "howloud_enabled", True)
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(response_text=QUIET_RESPONSE)

        # Act
        observation = fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )

        # Assert
        assert client.requests == []
        assert observation.status == "missing_api_key"

    def test_disabled_prevents_call(
        self, candidate_db, monkeypatch
    ):
        # Arrange
        monkeypatch.setenv(HOWLOUD_API_KEY_ENV_VAR, DUMMY_API_KEY)
        monkeypatch.setattr(config, "howloud_enabled", False)
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(response_text=QUIET_RESPONSE)

        # Act
        observation = fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )

        # Assert
        assert client.requests == []
        assert observation.status == "disabled"

    def test_successful_response_parsed(
        self, candidate_db, howloud_env
    ):
        # Arrange
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(
            response_text=QUIET_RESPONSE,
            response_content_type="application/json",
        )

        # Act
        observation = fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )

        # Assert
        assert observation.status == "ok"
        assert observation.noise_score == 92.0
        assert observation.raw_score_label == "Calm"
        assert observation.provider == PROVIDER_NAME

    def test_key_sent_in_header_not_query(
        self, candidate_db, howloud_env
    ):
        # Query strings land in server and proxy logs.
        # Arrange
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(
            response_text=QUIET_RESPONSE,
            response_content_type="application/json",
        )

        # Act
        fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )

        # Assert
        sent = client.requests[0]
        assert sent.headers[API_KEY_HEADER] == DUMMY_API_KEY
        assert DUMMY_API_KEY not in sent.url

    def test_http_error_captured_safely(
        self, candidate_db, howloud_env
    ):
        # Arrange
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(
            response_status=403,
            response_text="forbidden",
        )

        # Act
        observation = fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )

        # Assert
        assert observation.status == "http_error"
        assert "403" in observation.error_message
        assert DUMMY_API_KEY not in observation.error_message

    def test_timeout_captured(self, candidate_db, howloud_env):
        # Arrange
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(response_timed_out=True)

        # Act
        observation = fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )

        # Assert
        assert observation.status == "timeout"

    def test_timeout_is_configured_on_request(
        self, candidate_db, howloud_env
    ):
        # Arrange
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(
            response_text=QUIET_RESPONSE,
            response_content_type="application/json",
        )

        # Act
        fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )

        # Assert
        assert client.requests[0].timeout_seconds == (
            config.howloud_timeout_seconds
        )

    def test_key_redacted_from_echoed_response(
        self, candidate_db, howloud_env
    ):
        # A provider that echoes the key back must not get it stored.
        # Arrange
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        echoed = json.dumps({
            "status": "OK",
            "sentKey": DUMMY_API_KEY,
            "result": {"score": 90, "scoretext": "Calm"},
        })
        client = FakeHttpClient(
            response_text=echoed,
            response_content_type="application/json",
        )

        # Act
        observation = fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )

        # Assert
        assert observation.status == "ok"
        assert DUMMY_API_KEY not in (
            observation.raw_response_json or ""
        )
        assert "[REDACTED]" in observation.raw_response_json


class TestPersistence:
    """Observation storage."""

    def test_save_and_retrieve_latest(
        self, candidate_db, howloud_env
    ):
        # Act
        _save_observation(candidate_db, 5, QUIET_RESPONSE)
        latest = get_latest_howloud_observation(
            5, db_path=candidate_db
        )

        # Assert
        assert latest is not None
        assert latest.noise_score == 92.0

    def test_latest_returns_most_recent(
        self, candidate_db, howloud_env
    ):
        # Act
        _save_observation(candidate_db, 5, QUIET_RESPONSE)
        _save_observation(candidate_db, 5, LOUD_RESPONSE)
        latest = get_latest_howloud_observation(
            5, db_path=candidate_db
        )

        # Assert
        assert latest.noise_score == 62.0

    def test_none_when_no_observation(self, candidate_db):
        # Assert
        assert get_latest_howloud_observation(
            5, db_path=candidate_db
        ) is None

    def test_failed_observations_saved_for_audit(
        self, candidate_db, howloud_env
    ):
        # Arrange
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(response_status=500)
        observation = fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )

        # Act
        save_howloud_observation(observation, db_path=candidate_db)

        # Assert: stored, but not treated as a usable reading
        assert get_latest_howloud_observation(
            5, db_path=candidate_db
        ) is None
        assert get_latest_howloud_observation(
            5, db_path=candidate_db, successful_only=False
        ).status == "http_error"

    def test_saving_does_not_touch_redfin_fields(
        self, candidate_db, howloud_env
    ):
        # Arrange
        conn = sqlite3.connect(candidate_db)
        before = conn.execute(
            "SELECT quiet_score, vibrancy_score, "
            "quiet_gatekeeper_result FROM candidate_review_queue "
            "WHERE candidate_id = 5"
        ).fetchone()
        conn.close()

        # Act
        _save_observation(candidate_db, 5, LOUD_RESPONSE)

        # Assert
        conn = sqlite3.connect(candidate_db)
        after = conn.execute(
            "SELECT quiet_score, vibrancy_score, "
            "quiet_gatekeeper_result FROM candidate_review_queue "
            "WHERE candidate_id = 5"
        ).fetchone()
        conn.close()
        assert before == after
        assert after == (6.9, 1.1, "fail_noise_risk")


class TestComparison:
    """Comparison never blends the two sources."""

    def test_agreement_when_both_quiet(
        self, candidate_db, howloud_env
    ):
        # Arrange: candidate 4 has Redfin Quiet 9.9
        _save_observation(candidate_db, 4, QUIET_RESPONSE)

        # Act
        result = compare_howloud_to_redfin(
            4, db_path=candidate_db
        )

        # Assert
        assert result.agreement_level == AGREEMENT_CLEAR
        assert result.needs_manual_review is False

    def test_possible_disagreement_quiet_redfin_loud_howloud(
        self, candidate_db, howloud_env
    ):
        # Arrange: Redfin says quiet (9.9), HowLoud says busy
        _save_observation(candidate_db, 4, LOUD_RESPONSE)

        # Act
        result = compare_howloud_to_redfin(
            4, db_path=candidate_db
        )

        # Assert
        assert result.agreement_level == POSSIBLE_DISAGREEMENT
        assert result.needs_manual_review is True
        assert "Review manually" in result.comparison_note

    def test_missing_redfin_score(
        self, candidate_db, howloud_env
    ):
        # Arrange: candidate 8 has no Redfin scores
        _save_observation(candidate_db, 8, QUIET_RESPONSE)

        # Act
        result = compare_howloud_to_redfin(
            8, db_path=candidate_db
        )

        # Assert
        assert result.agreement_level == MISSING_REDFIN_SCORE
        assert result.needs_manual_review is True

    def test_missing_howloud_score(self, candidate_db):
        # Act
        result = compare_howloud_to_redfin(
            4, db_path=candidate_db
        )

        # Assert
        assert result.agreement_level == MISSING_HOWLOUD_SCORE
        assert result.howloud_noise_score is None

    def test_inconclusive_reading_needs_manual_review(
        self, candidate_db, howloud_env
    ):
        # Arrange: mid-band score with an unfamiliar label
        ambiguous = json.dumps({
            "status": "OK",
            "result": {"score": 75, "scoretext": "Moderate"},
        })
        _save_observation(candidate_db, 4, ambiguous)

        # Act
        result = compare_howloud_to_redfin(
            4, db_path=candidate_db
        )

        # Assert
        assert result.agreement_level == MANUAL_REVIEW_NEEDED
        assert result.needs_manual_review is True

    def test_gatekeeper_failure_remains_failure(
        self, candidate_db, howloud_env
    ):
        # Candidate 5 fails the gatekeeper. A calm HowLoud reading
        # must not change that.
        # Arrange
        _save_observation(candidate_db, 5, QUIET_RESPONSE)

        # Act
        result = compare_howloud_to_redfin(
            5, db_path=candidate_db
        )

        # Assert
        assert result.redfin_gatekeeper_result == "fail_noise_risk"
        assert "does not change the gatekeeper result" in (
            result.gatekeeper_note
        )

        conn = sqlite3.connect(candidate_db)
        stored = conn.execute(
            "SELECT quiet_gatekeeper_result FROM "
            "candidate_review_queue WHERE candidate_id = 5"
        ).fetchone()[0]
        conn.close()
        assert stored == "fail_noise_risk"

    def test_comparison_reports_both_sources_separately(
        self, candidate_db, howloud_env
    ):
        # Arrange
        _save_observation(candidate_db, 5, LOUD_RESPONSE)

        # Act
        result = compare_howloud_to_redfin(
            5, db_path=candidate_db
        )

        # Assert: both present, neither merged into the other
        assert result.redfin_quiet_score == 6.9
        assert result.howloud_noise_score == 62.0

    def test_comparison_makes_no_purchase_recommendation(
        self, candidate_db, howloud_env
    ):
        # Arrange
        _save_observation(candidate_db, 5, LOUD_RESPONSE)

        # Act
        result = compare_howloud_to_redfin(
            5, db_path=candidate_db
        )
        text = (
            f"{result.comparison_note} {result.gatekeeper_note}"
        ).lower()

        # Assert
        for banned in ["you should buy", "recommend buying", "bid"]:
            assert banned not in text

    def test_missing_candidate_handled(self, candidate_db):
        # Act
        result = compare_howloud_to_redfin(
            999, db_path=candidate_db
        )

        # Assert
        assert "not found" in result.comparison_note


class TestEnrichmentOrchestration:
    """enrich_candidate_with_howloud."""

    def test_dry_run_makes_no_call_and_no_write(
        self, candidate_db, howloud_env
    ):
        # Act
        result = enrich_candidate_with_howloud(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db, dry_run=True,
        )

        # Assert
        assert result.dry_run is True
        assert result.network_call_performed is False
        assert howloud_table_exists(candidate_db) is False

    def test_dry_run_reports_endpoint(
        self, candidate_db, howloud_env
    ):
        # Act
        result = enrich_candidate_with_howloud(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db, dry_run=True,
        )

        # Assert
        assert "api.howloud.com" in result.request.endpoint_url

    def test_real_run_requires_configuration(
        self, candidate_db, no_howloud_env
    ):
        # Act
        result = enrich_candidate_with_howloud(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db, dry_run=False,
        )

        # Assert
        assert result.success is False
        assert result.status == "missing_api_key"
        assert result.network_call_performed is False

    def test_real_run_saves_observation(
        self, candidate_db, howloud_env
    ):
        # Arrange
        client = FakeHttpClient(
            response_text=QUIET_RESPONSE,
            response_content_type="application/json",
        )

        # Act
        result = enrich_candidate_with_howloud(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db, dry_run=False,
            http_client=client,
        )

        # Assert
        assert result.success is True
        assert result.observation.observation_id
        assert "Redfin scores unchanged" in result.detail

    def test_invalid_request_short_circuits(
        self, candidate_db, howloud_env
    ):
        # Act: no coordinates
        result = enrich_candidate_with_howloud(
            5, db_path=candidate_db, dry_run=False
        )

        # Assert
        assert result.success is False
        assert result.status == "invalid_request"
        assert result.network_call_performed is False


class TestListingCandidates:
    """list_candidates_needing_howloud."""

    def test_lists_all_when_no_observations(self, candidate_db):
        # Act
        rows = list_candidates_needing_howloud(candidate_db)

        # Assert
        assert [r["candidate_id"] for r in rows] == [4, 5, 8]
        assert all(
            r["has_coordinates"] is False for r in rows
        )

    def test_excludes_successfully_enriched(
        self, candidate_db, howloud_env
    ):
        # Arrange
        _save_observation(candidate_db, 5, QUIET_RESPONSE)

        # Act
        rows = list_candidates_needing_howloud(candidate_db)

        # Assert
        assert 5 not in [r["candidate_id"] for r in rows]

    def test_failed_attempt_still_needs_enrichment(
        self, candidate_db, howloud_env
    ):
        # Arrange
        request = build_howloud_request_for_candidate(
            5, latitude=33.4, longitude=-117.1,
            db_path=candidate_db,
        )
        client = FakeHttpClient(response_status=500)
        observation = fetch_howloud_noise(
            request, http_client=client, allow_network=True
        )
        save_howloud_observation(observation, db_path=candidate_db)

        # Act
        rows = list_candidates_needing_howloud(candidate_db)

        # Assert
        assert 5 in [r["candidate_id"] for r in rows]

    def test_listing_creates_no_table(self, candidate_db):
        # Act
        list_candidates_needing_howloud(candidate_db)

        # Assert
        assert howloud_table_exists(candidate_db) is False


class TestReports:
    """HowLoud noise report export."""

    def test_csv_export(self, candidate_db, howloud_env, tmp_path):
        # Arrange
        _save_observation(candidate_db, 5, LOUD_RESPONSE)

        # Act
        paths = export_howloud_noise_report(
            db_path=candidate_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="csv",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        for column in [
            "candidate_id",
            "redfin_quiet_score",
            "howloud_noise_score",
            "agreement_level",
            "needs_manual_review",
            "gatekeeper_note",
        ]:
            assert column in content

    def test_markdown_export_with_clickable_link(
        self, candidate_db, howloud_env, tmp_path
    ):
        # Arrange
        _save_observation(candidate_db, 5, LOUD_RESPONSE)

        # Act
        paths = export_howloud_noise_report(
            db_path=candidate_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert "# HowLoud Noise Report" in content
        assert "[View](" in content
        assert "redfin.com" in content

    def test_report_states_separation_and_gatekeeper(
        self, candidate_db, howloud_env, tmp_path
    ):
        # Arrange
        _save_observation(candidate_db, 5, LOUD_RESPONSE)

        # Act
        paths = export_howloud_noise_report(
            db_path=candidate_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="md",
        )
        content = Path(paths[0]).read_text(encoding="utf-8")

        # Assert
        assert "never blended" in content
        assert "gatekeeper" in content.lower()

    def test_report_contains_no_api_key(
        self, candidate_db, howloud_env, tmp_path
    ):
        # Arrange
        _save_observation(candidate_db, 5, LOUD_RESPONSE)

        # Act
        paths = export_howloud_noise_report(
            db_path=candidate_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="both",
        )

        # Assert
        for path in paths:
            assert DUMMY_API_KEY not in Path(path).read_text(
                encoding="utf-8"
            )

    def test_export_both_formats(
        self, candidate_db, howloud_env, tmp_path
    ):
        # Act
        paths = export_howloud_noise_report(
            db_path=candidate_db,
            exports_dir=str(tmp_path / "exports"),
            fmt="both",
        )

        # Assert
        assert len(paths) == 2

    def test_export_does_not_mutate_candidates(
        self, candidate_db, howloud_env, tmp_path
    ):
        # Arrange
        conn = sqlite3.connect(candidate_db)
        before = conn.execute(
            "SELECT quiet_score, quiet_gatekeeper_result "
            "FROM candidate_review_queue ORDER BY candidate_id"
        ).fetchall()
        conn.close()

        # Act
        export_howloud_noise_report(
            db_path=candidate_db,
            exports_dir=str(tmp_path / "exports"),
        )

        # Assert
        conn = sqlite3.connect(candidate_db)
        after = conn.execute(
            "SELECT quiet_score, quiet_gatekeeper_result "
            "FROM candidate_review_queue ORDER BY candidate_id"
        ).fetchall()
        conn.close()
        assert before == after


class TestCliCommands:
    """CLI surface."""

    @pytest.mark.parametrize("command_name", HOWLOUD_COMMANDS)
    def test_command_registered(self, command_name):
        # Assert
        assert command_name in _command_map()

    @pytest.mark.parametrize("command_name", HOWLOUD_COMMANDS)
    def test_canonical_db_default(self, command_name):
        # Act
        default = _db_default(_command_map()[command_name])

        # Assert
        assert default == config.database_path
        assert default == "db/marketsentry.db"

    def test_config_status_no_key(self, no_howloud_env):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["howloud-config-status"])

        # Assert
        assert result.exit_code == 0
        assert "not set" in result.output

    def test_config_status_masked_key(self, howloud_env):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(app, ["howloud-config-status"])

        # Assert
        assert result.exit_code == 0
        assert DUMMY_API_KEY not in result.output
        assert "9999" in result.output

    def test_list_candidates_needing_howloud(self, candidate_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "list-candidates-needing-howloud",
                "--db", candidate_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Total: 3" in result.output

    def test_enrich_dry_run(self, candidate_db, howloud_env):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "enrich-candidate-howloud",
                "--candidate-id", "5",
                "--lat", "33.4936",
                "--lng", "-117.1484",
                "--db", candidate_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "dry-run" in result.output
        assert "Network call: no" in result.output
        assert howloud_table_exists(candidate_db) is False

    def test_enrich_missing_key_exits_nonzero(
        self, candidate_db, no_howloud_env
    ):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "enrich-candidate-howloud",
                "--candidate-id", "5",
                "--lat", "33.4936",
                "--lng", "-117.1484",
                "--db", candidate_db,
                "--no-dry-run",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "No API key configured" in result.output

    def test_compare_command(self, candidate_db, howloud_env):
        # Arrange
        _save_observation(candidate_db, 5, LOUD_RESPONSE)
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "compare-howloud-redfin",
                "--candidate-id", "5",
                "--db", candidate_db,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "fail_noise_risk" in result.output
        assert "does not change the gatekeeper" in result.output

    def test_export_command(
        self, candidate_db, howloud_env, tmp_path
    ):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "export-howloud-noise-report",
                "--db", candidate_db,
                "--output-dir", str(tmp_path / "exports"),
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Exported" in result.output

    def test_no_command_output_contains_key(
        self, candidate_db, howloud_env, tmp_path
    ):
        # Arrange
        runner = CliRunner()

        # Act
        outputs = []
        for args in (
            ["howloud-config-status"],
            [
                "list-candidates-needing-howloud",
                "--db", candidate_db,
            ],
            [
                "enrich-candidate-howloud",
                "--candidate-id", "5",
                "--lat", "33.4", "--lng", "-117.1",
                "--db", candidate_db,
            ],
            [
                "compare-howloud-redfin",
                "--candidate-id", "5",
                "--db", candidate_db,
            ],
            [
                "export-howloud-noise-report",
                "--db", candidate_db,
                "--output-dir", str(tmp_path / "exports"),
            ],
        ):
            outputs.append(runner.invoke(app, args).output)

        # Assert
        for output in outputs:
            assert DUMMY_API_KEY not in output

    def test_custom_db_accepted(self, candidate_db):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(
            app,
            [
                "list-candidates-needing-howloud",
                "--db", candidate_db,
            ],
        )

        # Assert
        assert "No such option" not in result.output
        assert result.exit_code == 0


class TestDashboardSection:
    """Dashboard exposes HowLoud without calling it on load."""

    def test_section_present(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "HowLoud Noise Enrichment" in content
        assert "howloud_enrich_form" in content
        assert "howloud_dry_run_form" in content
        assert "howloud_export_form" in content

    def test_no_network_call_on_load(self):
        # Every enrichment call must sit after a submit guard, so
        # rendering the page cannot trigger a request.
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")
        lines = content.split("\n")

        submit_lines = [
            i
            for i, line in enumerate(lines)
            if "_hl_dr_submit:" in line
            or "_hl_en_submit:" in line
        ]
        call_lines = [
            i
            for i, line in enumerate(lines)
            if "enrich_candidate_with_howloud(" in line
            and not line.strip().startswith(
                "enrich_candidate_with_howloud,"
            )
        ]

        # Assert
        assert submit_lines
        assert call_lines
        for call_line in call_lines:
            assert any(
                submit < call_line for submit in submit_lines
            ), f"unguarded HowLoud call at line {call_line + 1}"

    def test_dry_run_default_in_dashboard_preview(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "dry_run=True" in content
        assert "howloud_en_confirm" in content

    def test_masked_key_displayed(self):
        # Arrange
        content = (
            SRC_DIR / "dashboard_app.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "api_key_masked" in content

    def test_dashboard_imports(self):
        # Act
        import marketsentry.dashboard_app as dash

        # Assert
        assert dash is not None


class TestSafetyInvariants:
    """Milestone 55 adds no unsafe capability."""

    def test_no_browser_automation(self):
        # Arrange
        source = _strip_prose(
            (SRC_DIR / "howloud_adapter.py").read_text(
                encoding="utf-8"
            )
        )

        # Assert
        for banned in [
            "playwright",
            "selenium",
            "webdriver",
            "webbrowser",
            "chromium",
        ]:
            assert banned not in source.lower()

    def test_no_redfin_scraping(self):
        # Arrange
        source = (
            SRC_DIR / "howloud_adapter.py"
        ).read_text(encoding="utf-8")

        # Assert
        for banned in [
            "redfin.com/stingray",
            "BeautifulSoup",
            "html.parser",
        ]:
            assert banned not in source

    def test_no_outbound_notifications(self):
        # Arrange
        source = _strip_prose(
            (SRC_DIR / "howloud_adapter.py").read_text(
                encoding="utf-8"
            )
        )

        # Assert
        for banned in ["smtp", "send_email", "webhook", "sms"]:
            assert banned not in source.lower()

    def test_no_walkability_fields(self):
        # Arrange
        source = _strip_prose(
            (SRC_DIR / "howloud_adapter.py").read_text(
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
            assert banned not in source.lower()

    def test_observation_model_has_no_walkability(self):
        # Act
        fields = HowLoudObservation.model_fields.keys()

        # Assert
        for banned in ["walk", "transit", "bike"]:
            assert not any(banned in f for f in fields)

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

    def test_howloud_does_not_appear_in_gatekeeper_module(self):
        # The gatekeeper must remain unaware of HowLoud entirely.
        # Arrange
        source = (
            SRC_DIR / "quiet_vibrancy.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "howloud" not in source.lower()

    def test_adapter_never_writes_candidate_table(self):
        # Arrange
        source = (
            SRC_DIR / "howloud_adapter.py"
        ).read_text(encoding="utf-8")

        # Assert: no UPDATE or INSERT against Redfin-owned tables
        lowered = source.lower()
        assert "update candidate_review_queue" not in lowered
        assert "insert into candidate_review_queue" not in lowered
        assert "update watched_properties" not in lowered

    def test_module_uses_shared_http_abstraction(self):
        # Guarantees tests can mock every outbound call.
        # Arrange
        source = (
            SRC_DIR / "howloud_adapter.py"
        ).read_text(encoding="utf-8")

        # Assert
        assert "source_adapters.http_client" in source
        assert "import requests" not in source
        assert "import httpx" not in source
