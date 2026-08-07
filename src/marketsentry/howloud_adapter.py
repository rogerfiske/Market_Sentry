"""HowLoud noise enrichment adapter.

Supplements Redfin Quiet/Vibrancy and local operator knowledge with a
separately stored third-party noise signal from HowLoud.

Design constraints that shaped this module:

- **Opt-in only.** No network call happens unless an operator runs an
  explicit command with enrichment enabled and a key configured.
  Dry-run is the default posture and performs no request.
- **Never blended with Redfin.** HowLoud values live in their own table
  and are never converted onto the Redfin Quiet scale. The Quiet Score
  gatekeeper is untouched: HowLoud can support a manual review, it can
  never change a pass or fail.
- **The API key is never persisted.** It is read from the environment,
  placed directly into a request header, and never stored, logged,
  echoed, or written into any report or raw response record.
- **Coordinate-based.** The HowLoud v2 API accepts latitude/longitude
  only; it has no address endpoint. Coordinates are supplied by the
  operator and stored with the observation for reuse. No geocoding
  service is called, because that would add a second network
  dependency this milestone does not authorize.

This module does NOT perform Redfin retrieval or scraping, browser
automation, outbound notifications, or credential storage, and does not
add walkability fields.
"""

import csv
import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.config import config, get_howloud_api_key, mask_secret

PROVIDER_NAME = "HowLoud"
PROVIDER_API_VERSION = "v2"
SCORE_ENDPOINT_PATH = "/v2/score"

# HowLoud sends the key in this header. Also accepted as a query
# parameter, which is deliberately not used: query strings end up in
# server logs and proxy logs.
API_KEY_HEADER = "x-api-key"

# Provider text labels, calmest first. HowLoud's own wording is the
# most reliable signal available because the numeric scales differ
# between the overall score and the per-source values.
QUIET_LEANING_LABELS = {"calm", "quiet"}
LOUD_LEANING_LABELS = {"busy", "noisy", "loud", "very active"}

# Overall SoundScore is documented as higher-is-quieter on a 0-100
# scale. These bands are used only to categorize agreement for manual
# review; they never feed the gatekeeper.
HOWLOUD_QUIET_LEANING_MIN = 80.0
HOWLOUD_LOUD_LEANING_MAX = 70.0

AGREEMENT_CLEAR = "agreement_clear"
POSSIBLE_DISAGREEMENT = "possible_disagreement"
MISSING_REDFIN_SCORE = "missing_redfin_score"
MISSING_HOWLOUD_SCORE = "missing_howloud_score"
MANUAL_REVIEW_NEEDED = "manual_review_needed"


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------


class HowLoudConfigStatus(BaseModel):
    """Configuration state, safe to print.

    Never carries the API key itself, only whether one is present and
    a masked display form.
    """

    enabled: bool = False
    api_key_present: bool = False
    api_key_masked: str = "not set"
    base_url: str = ""
    timeout_seconds: int = 0
    ready: bool = False
    messages: List[str] = Field(default_factory=list)


class HowLoudAddressRequest(BaseModel):
    """A prepared HowLoud lookup for one property.

    Named for the operator's mental model (they are enriching an
    address), but the provider is queried by coordinates because the
    v2 API has no address endpoint.
    """

    candidate_id: Optional[int] = None
    watched_property_id: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    request_source: str = "candidate"
    endpoint_url: str = ""
    is_ready: bool = False
    blocking_reasons: List[str] = Field(default_factory=list)


class HowLoudObservation(BaseModel):
    """One stored HowLoud reading, kept separate from Redfin fields."""

    observation_id: Optional[int] = None
    candidate_id: Optional[int] = None
    watched_property_id: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    request_source: str = "candidate"
    noise_score: Optional[float] = None
    traffic_score: Optional[float] = None
    airport_score: Optional[float] = None
    locality_score: Optional[float] = None
    raw_score_label: Optional[str] = None
    traffic_label: Optional[str] = None
    airport_label: Optional[str] = None
    locality_label: Optional[str] = None
    provider: str = PROVIDER_NAME
    provider_version: str = PROVIDER_API_VERSION
    raw_response_json: Optional[str] = None
    confidence: Optional[float] = None
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HowLoudEnrichmentResult(BaseModel):
    """Outcome of one enrichment attempt."""

    candidate_id: Optional[int] = None
    dry_run: bool = True
    network_call_performed: bool = False
    success: bool = False
    observation: Optional[HowLoudObservation] = None
    request: Optional[HowLoudAddressRequest] = None
    status: str = "not_run"
    detail: str = ""
    errors: List[str] = Field(default_factory=list)


class HowLoudComparisonResult(BaseModel):
    """Neutral side-by-side of Redfin and HowLoud evidence.

    The two sources are reported next to each other, never merged.
    """

    candidate_id: Optional[int] = None
    address: Optional[str] = None
    redfin_url: Optional[str] = None
    redfin_quiet_score: Optional[float] = None
    redfin_vibrancy_score: Optional[float] = None
    redfin_gatekeeper_result: Optional[str] = None
    howloud_noise_score: Optional[float] = None
    howloud_traffic_score: Optional[float] = None
    howloud_airport_score: Optional[float] = None
    howloud_locality_score: Optional[float] = None
    howloud_score_label: Optional[str] = None
    howloud_observed_at: Optional[str] = None
    agreement_level: str = MISSING_HOWLOUD_SCORE
    comparison_note: str = ""
    needs_manual_review: bool = False
    gatekeeper_note: str = ""


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------


def get_howloud_config_status() -> HowLoudConfigStatus:
    """Report HowLoud configuration without exposing the key.

    Returns:
        Status describing whether enrichment can run.
    """
    api_key = get_howloud_api_key()
    status = HowLoudConfigStatus(
        enabled=config.howloud_enabled,
        api_key_present=api_key is not None,
        api_key_masked=mask_secret(api_key),
        base_url=config.howloud_base_url,
        timeout_seconds=config.howloud_timeout_seconds,
    )

    if not status.api_key_present:
        status.messages.append(
            "No API key configured. Set "
            "MARKETSENTRY_HOWLOUD_API_KEY in your environment or "
            ".env file. The key is never printed or stored."
        )
    if not status.enabled:
        status.messages.append(
            "HowLoud enrichment is disabled. Set "
            "MARKETSENTRY_HOWLOUD_ENABLED=true to allow explicit "
            "enrichment commands to make requests."
        )

    status.ready = status.enabled and status.api_key_present
    if status.ready:
        status.messages.append(
            "Ready. Enrichment still requires an explicit command; "
            "dry-run performs no request."
        )

    return status


# -------------------------------------------------------------------
# Schema
# -------------------------------------------------------------------


def howloud_table_exists(db_path: Optional[str] = None) -> bool:
    """Check whether the observations table exists, without creating it.

    Read paths use this instead of ensure_howloud_schema so that a
    dry-run performs no schema change of any kind.

    Args:
        db_path: Path to SQLite database.

    Returns:
        True when the table is present.
    """
    path = db_path or config.database_path
    if not Path(path).exists():
        return False

    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='howloud_observations'"
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def ensure_howloud_schema(db_path: Optional[str] = None) -> None:
    """Create the howloud_observations table if absent.

    Idempotent. HowLoud values live here and never in the Redfin
    candidate or watchlist columns.

    Args:
        db_path: Path to SQLite database.
    """
    path = db_path or config.database_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS howloud_observations (
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                watched_property_id INTEGER,
                address TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                latitude REAL,
                longitude REAL,
                request_source TEXT,
                noise_score REAL,
                traffic_score REAL,
                airport_score REAL,
                locality_score REAL,
                raw_score_label TEXT,
                traffic_label TEXT,
                airport_label TEXT,
                locality_label TEXT,
                provider TEXT DEFAULT 'HowLoud',
                provider_version TEXT,
                raw_response_json TEXT,
                confidence REAL,
                status TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for statement in (
            "CREATE INDEX IF NOT EXISTS idx_howloud_candidate "
            "ON howloud_observations(candidate_id)",
            "CREATE INDEX IF NOT EXISTS idx_howloud_watched "
            "ON howloud_observations(watched_property_id)",
            "CREATE INDEX IF NOT EXISTS idx_howloud_status "
            "ON howloud_observations(status)",
            "CREATE INDEX IF NOT EXISTS idx_howloud_created "
            "ON howloud_observations(created_at)",
        ):
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()


# -------------------------------------------------------------------
# Request building
# -------------------------------------------------------------------


def build_howloud_request_for_candidate(
    candidate_id: int,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    db_path: Optional[str] = None,
) -> HowLoudAddressRequest:
    """Prepare a HowLoud lookup for one candidate.

    Read-only and offline. Reuses coordinates from the most recent
    observation when the caller does not supply them, so an operator
    types them once per property.

    Args:
        candidate_id: Candidate ID.
        latitude: Latitude supplied by the operator.
        longitude: Longitude supplied by the operator.
        db_path: Path to SQLite database.

    Returns:
        Prepared request, with blocking reasons when not ready.
    """
    path = db_path or config.database_path
    request = HowLoudAddressRequest(
        candidate_id=candidate_id,
        latitude=latitude,
        longitude=longitude,
    )

    if not Path(path).exists():
        request.blocking_reasons.append(
            f"Database not found at {path}."
        )
        return request

    # Deliberately does not create the table: preparing a request is a
    # read, and a dry-run must not change the database at all.
    has_observations = howloud_table_exists(db_path=path)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT address, city, zip FROM candidate_review_queue "
            "WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            request.blocking_reasons.append(
                f"Candidate {candidate_id} not found."
            )
            return request

        request.address = row["address"]
        request.city = row["city"]
        request.zip = row["zip"]
        request.state = "CA"

        if has_observations and (
            request.latitude is None or request.longitude is None
        ):
            prior = conn.execute(
                "SELECT latitude, longitude FROM "
                "howloud_observations "
                "WHERE candidate_id = ? "
                "AND latitude IS NOT NULL "
                "AND longitude IS NOT NULL "
                "ORDER BY observation_id DESC LIMIT 1",
                (candidate_id,),
            ).fetchone()
            if prior:
                request.latitude = (
                    request.latitude
                    if request.latitude is not None
                    else prior["latitude"]
                )
                request.longitude = (
                    request.longitude
                    if request.longitude is not None
                    else prior["longitude"]
                )
    finally:
        conn.close()

    if request.latitude is None or request.longitude is None:
        request.blocking_reasons.append(
            "Latitude and longitude are required. The HowLoud v2 API "
            "accepts coordinates only; it has no address endpoint. "
            "Supply --lat and --lng."
        )
    else:
        if not (-90.0 <= request.latitude <= 90.0):
            request.blocking_reasons.append(
                f"Latitude {request.latitude} is out of range "
                "(-90 to 90)."
            )
        if not (-180.0 <= request.longitude <= 180.0):
            request.blocking_reasons.append(
                f"Longitude {request.longitude} is out of range "
                "(-180 to 180)."
            )

    if not request.blocking_reasons:
        request.endpoint_url = (
            f"{config.howloud_base_url.rstrip('/')}"
            f"{SCORE_ENDPOINT_PATH}"
            f"?lat={request.latitude}&lng={request.longitude}"
        )
        request.is_ready = True

    return request


# -------------------------------------------------------------------
# Response parsing
# -------------------------------------------------------------------


def _extract_result_block(payload: Any) -> Optional[Dict[str, Any]]:
    """Pull the score block out of a HowLoud response.

    The OpenAPI schema documents ``result`` as an object, but the
    provider's own Python sample reads ``res['result'][0]['score']``.
    Both shapes are accepted rather than trusting one.
    """
    if not isinstance(payload, dict):
        return None

    result = payload.get("result")
    if isinstance(result, dict):
        return result
    if isinstance(result, list) and result:
        first = result[0]
        return first if isinstance(first, dict) else None
    return None


def _as_float(value: Any) -> Optional[float]:
    """Coerce a provider value to float, or None when unusable."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_howloud_response(
    response_text: str,
) -> Dict[str, Any]:
    """Parse a HowLoud score response into flat fields.

    Args:
        response_text: Raw JSON body.

    Returns:
        Dict with parsed values plus a ``parse_error`` key when the
        payload could not be understood.
    """
    parsed: Dict[str, Any] = {
        "noise_score": None,
        "traffic_score": None,
        "airport_score": None,
        "locality_score": None,
        "raw_score_label": None,
        "traffic_label": None,
        "airport_label": None,
        "locality_label": None,
        "provider_status": None,
        "parse_error": None,
    }

    try:
        payload = json.loads(response_text)
    except (ValueError, TypeError) as exc:
        parsed["parse_error"] = f"Response was not valid JSON: {exc}"
        return parsed

    if isinstance(payload, dict):
        parsed["provider_status"] = payload.get("status")

    block = _extract_result_block(payload)
    if block is None:
        parsed["parse_error"] = (
            "Response did not contain a usable result block."
        )
        return parsed

    parsed["noise_score"] = _as_float(block.get("score"))
    parsed["traffic_score"] = _as_float(block.get("traffic"))
    parsed["airport_score"] = _as_float(block.get("airports"))
    parsed["locality_score"] = _as_float(block.get("local"))
    parsed["raw_score_label"] = block.get("scoretext")
    parsed["traffic_label"] = block.get("traffictext")
    parsed["airport_label"] = block.get("airportstext")
    parsed["locality_label"] = block.get("localtext")

    return parsed


# -------------------------------------------------------------------
# Fetch
# -------------------------------------------------------------------


def fetch_howloud_noise(
    request: HowLoudAddressRequest,
    http_client: Optional[Any] = None,
    allow_network: bool = False,
) -> HowLoudObservation:
    """Fetch a HowLoud reading for a prepared request.

    Performs no request unless ``allow_network`` is True, enrichment is
    enabled, and a key is configured. The key travels only in the
    request header and is never stored or returned.

    Args:
        request: Prepared request from build_howloud_request_for_candidate.
        http_client: HttpClient to use. Tests pass FakeHttpClient.
        allow_network: Explicit opt-in for the outbound call.

    Returns:
        Observation carrying parsed values or a safe error message.
    """
    from marketsentry.source_adapters.http_client import (
        HttpRequest,
        StandardLibraryHttpClient,
    )

    observation = HowLoudObservation(
        candidate_id=request.candidate_id,
        watched_property_id=request.watched_property_id,
        address=request.address,
        city=request.city,
        state=request.state,
        zip=request.zip,
        latitude=request.latitude,
        longitude=request.longitude,
        request_source=request.request_source,
        status="not_run",
    )

    if not request.is_ready:
        observation.status = "invalid_request"
        observation.error_message = "; ".join(
            request.blocking_reasons
        ) or "Request was not ready."
        return observation

    if not allow_network:
        observation.status = "dry_run"
        observation.error_message = None
        return observation

    if not config.howloud_enabled:
        observation.status = "disabled"
        observation.error_message = (
            "HowLoud enrichment is disabled. Set "
            "MARKETSENTRY_HOWLOUD_ENABLED=true to allow requests."
        )
        return observation

    api_key = get_howloud_api_key()
    if not api_key:
        observation.status = "missing_api_key"
        observation.error_message = (
            "No API key configured. Set "
            "MARKETSENTRY_HOWLOUD_API_KEY in your environment or "
            ".env file."
        )
        return observation

    client = http_client or StandardLibraryHttpClient()
    http_request = HttpRequest(
        url=request.endpoint_url,
        method="GET",
        headers={
            API_KEY_HEADER: api_key,
            "Accept": "application/json",
        },
        timeout_seconds=config.howloud_timeout_seconds,
    )

    try:
        response = client.get(http_request)
    except Exception as exc:
        observation.status = "error"
        observation.error_message = _sanitize_error(str(exc), api_key)
        return observation

    if response.timed_out:
        observation.status = "timeout"
        observation.error_message = (
            f"Request timed out after "
            f"{config.howloud_timeout_seconds}s."
        )
        return observation

    if response.error:
        observation.status = "error"
        observation.error_message = _sanitize_error(
            response.error, api_key
        )
        return observation

    if not response.is_success:
        observation.status = "http_error"
        observation.error_message = _sanitize_error(
            f"HowLoud returned HTTP {response.status_code}.",
            api_key,
        )
        return observation

    parsed = parse_howloud_response(response.text)
    if parsed["parse_error"]:
        observation.status = "parse_error"
        observation.error_message = _sanitize_error(
            parsed["parse_error"], api_key
        )
        return observation

    observation.noise_score = parsed["noise_score"]
    observation.traffic_score = parsed["traffic_score"]
    observation.airport_score = parsed["airport_score"]
    observation.locality_score = parsed["locality_score"]
    observation.raw_score_label = parsed["raw_score_label"]
    observation.traffic_label = parsed["traffic_label"]
    observation.airport_label = parsed["airport_label"]
    observation.locality_label = parsed["locality_label"]
    observation.raw_response_json = _sanitize_error(
        response.text, api_key
    )
    observation.status = "ok"
    observation.confidence = (
        1.0 if observation.noise_score is not None else 0.0
    )

    return observation


def _sanitize_error(text: str, api_key: Optional[str]) -> str:
    """Strip any occurrence of the API key from text before storing.

    A defence in depth measure. The key is never deliberately written
    anywhere, but provider errors and echoed request URLs can contain
    it, so every string headed for storage passes through here.
    """
    if not text:
        return ""
    cleaned = text
    if api_key:
        cleaned = cleaned.replace(api_key, "[REDACTED]")
    return cleaned


# -------------------------------------------------------------------
# Persistence
# -------------------------------------------------------------------


def save_howloud_observation(
    observation: HowLoudObservation,
    db_path: Optional[str] = None,
) -> int:
    """Persist one HowLoud observation.

    Writes only to howloud_observations. Never touches Redfin
    candidate or watchlist columns.

    Args:
        observation: Observation to store.
        db_path: Path to SQLite database.

    Returns:
        The new observation ID.
    """
    path = db_path or config.database_path
    ensure_howloud_schema(db_path=path)

    conn = sqlite3.connect(path)
    try:
        cursor = conn.execute(
            "INSERT INTO howloud_observations "
            "(candidate_id, watched_property_id, address, city, "
            "state, zip, latitude, longitude, request_source, "
            "noise_score, traffic_score, airport_score, "
            "locality_score, raw_score_label, traffic_label, "
            "airport_label, locality_label, provider, "
            "provider_version, raw_response_json, confidence, "
            "status, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?, ?, ?, ?)",
            (
                observation.candidate_id,
                observation.watched_property_id,
                observation.address,
                observation.city,
                observation.state,
                observation.zip,
                observation.latitude,
                observation.longitude,
                observation.request_source,
                observation.noise_score,
                observation.traffic_score,
                observation.airport_score,
                observation.locality_score,
                observation.raw_score_label,
                observation.traffic_label,
                observation.airport_label,
                observation.locality_label,
                observation.provider,
                observation.provider_version,
                observation.raw_response_json,
                observation.confidence,
                observation.status,
                observation.error_message,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def get_latest_howloud_observation(
    candidate_id: int,
    db_path: Optional[str] = None,
    successful_only: bool = True,
) -> Optional[HowLoudObservation]:
    """Return the most recent HowLoud observation for a candidate.

    Args:
        candidate_id: Candidate ID.
        db_path: Path to SQLite database.
        successful_only: Only consider observations with status 'ok'.

    Returns:
        The observation, or None when there is none.
    """
    path = db_path or config.database_path
    if not howloud_table_exists(db_path=path):
        return None

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        query = (
            "SELECT * FROM howloud_observations "
            "WHERE candidate_id = ?"
        )
        params: tuple = (candidate_id,)
        if successful_only:
            query += " AND status = 'ok'"
        query += " ORDER BY observation_id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        if row is None:
            return None
        return _row_to_observation(row)
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _row_to_observation(row: sqlite3.Row) -> HowLoudObservation:
    """Convert a database row into an observation model."""
    return HowLoudObservation(
        observation_id=row["observation_id"],
        candidate_id=row["candidate_id"],
        watched_property_id=row["watched_property_id"],
        address=row["address"],
        city=row["city"],
        state=row["state"],
        zip=row["zip"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        request_source=row["request_source"] or "candidate",
        noise_score=row["noise_score"],
        traffic_score=row["traffic_score"],
        airport_score=row["airport_score"],
        locality_score=row["locality_score"],
        raw_score_label=row["raw_score_label"],
        traffic_label=row["traffic_label"],
        airport_label=row["airport_label"],
        locality_label=row["locality_label"],
        provider=row["provider"] or PROVIDER_NAME,
        provider_version=row["provider_version"] or "",
        raw_response_json=row["raw_response_json"],
        confidence=row["confidence"],
        status=row["status"] or "",
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# -------------------------------------------------------------------
# Comparison
# -------------------------------------------------------------------


def _label_lean(label: Optional[str]) -> Optional[str]:
    """Classify a provider text label as quiet- or loud-leaning."""
    if not label:
        return None
    normalized = label.strip().lower()
    if normalized in QUIET_LEANING_LABELS:
        return "quiet"
    if normalized in LOUD_LEANING_LABELS:
        return "loud"
    return None


def _howloud_lean(
    observation: HowLoudObservation,
) -> Optional[str]:
    """Decide whether a HowLoud reading leans quiet or loud.

    Prefers the provider's own wording, because the numeric scales are
    not consistent between the overall score and the per-source values.
    Falls back to the documented higher-is-quieter overall score, and
    returns None when neither is conclusive.
    """
    label_lean = _label_lean(observation.raw_score_label)
    if label_lean:
        return label_lean

    score = observation.noise_score
    if score is None:
        return None
    if score >= HOWLOUD_QUIET_LEANING_MIN:
        return "quiet"
    if score <= HOWLOUD_LOUD_LEANING_MAX:
        return "loud"
    return None


def compare_howloud_to_redfin(
    candidate_id: int,
    db_path: Optional[str] = None,
) -> HowLoudComparisonResult:
    """Compare stored HowLoud evidence against Redfin scores.

    Reports the two sources side by side. Never merges them, never
    converts HowLoud onto the Redfin scale, and never changes the
    gatekeeper result.

    Args:
        candidate_id: Candidate ID.
        db_path: Path to SQLite database.

    Returns:
        Neutral comparison with an agreement category and a note.
    """
    path = db_path or config.database_path
    result = HowLoudComparisonResult(candidate_id=candidate_id)

    if not Path(path).exists():
        result.comparison_note = f"Database not found at {path}."
        return result

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT address, redfin_url, quiet_score, "
            "vibrancy_score, quiet_gatekeeper_result "
            "FROM candidate_review_queue WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        result.comparison_note = (
            f"Candidate {candidate_id} not found."
        )
        return result

    result.address = row["address"]
    result.redfin_url = row["redfin_url"]
    result.redfin_quiet_score = row["quiet_score"]
    result.redfin_vibrancy_score = row["vibrancy_score"]
    result.redfin_gatekeeper_result = row["quiet_gatekeeper_result"]

    observation = get_latest_howloud_observation(
        candidate_id, db_path=path
    )
    if observation is not None:
        result.howloud_noise_score = observation.noise_score
        result.howloud_traffic_score = observation.traffic_score
        result.howloud_airport_score = observation.airport_score
        result.howloud_locality_score = observation.locality_score
        result.howloud_score_label = observation.raw_score_label
        result.howloud_observed_at = observation.created_at

    # The gatekeeper statement is emitted regardless of agreement, so
    # no reader can conclude HowLoud changed the outcome.
    if result.redfin_gatekeeper_result == "fail_noise_risk":
        result.gatekeeper_note = (
            "Redfin Quiet is below the gatekeeper threshold. HowLoud "
            "can provide supporting context but does not change the "
            "gatekeeper result."
        )
    elif result.redfin_gatekeeper_result == "pass":
        result.gatekeeper_note = (
            "Redfin Quiet meets the gatekeeper threshold. HowLoud is "
            "additional evidence and does not change that result."
        )
    else:
        result.gatekeeper_note = (
            "No Redfin gatekeeper result recorded. HowLoud does not "
            "substitute for the Redfin Quiet score."
        )

    if result.redfin_quiet_score is None:
        result.agreement_level = MISSING_REDFIN_SCORE
        result.needs_manual_review = True
        result.comparison_note = (
            "No Redfin Quiet score recorded, so the two sources "
            "cannot be compared. Enter the Redfin Quiet score first."
        )
        return result

    if observation is None or observation.noise_score is None:
        result.agreement_level = MISSING_HOWLOUD_SCORE
        result.needs_manual_review = False
        result.comparison_note = (
            "No HowLoud reading recorded for this candidate."
        )
        return result

    redfin_quiet_lean = (
        "quiet"
        if result.redfin_quiet_score >= config.quiet_score_minimum
        else "loud"
    )
    howloud_lean = _howloud_lean(observation)
    traffic_lean = _label_lean(observation.traffic_label)
    airport_lean = _label_lean(observation.airport_label)

    if howloud_lean is None:
        result.agreement_level = MANUAL_REVIEW_NEEDED
        result.needs_manual_review = True
        result.comparison_note = (
            f"HowLoud reported a soundscore of "
            f"{observation.noise_score} without a conclusive "
            "category. Review both sources manually."
        )
        return result

    if howloud_lean == redfin_quiet_lean:
        result.agreement_level = AGREEMENT_CLEAR
        result.needs_manual_review = False
        result.comparison_note = (
            f"Both sources lean {howloud_lean}. Redfin Quiet "
            f"{result.redfin_quiet_score} and HowLoud soundscore "
            f"{observation.noise_score} point the same direction."
        )
    else:
        result.agreement_level = POSSIBLE_DISAGREEMENT
        result.needs_manual_review = True
        if redfin_quiet_lean == "quiet":
            result.comparison_note = (
                "HowLoud indicates elevated noise while Redfin Quiet "
                f"is {result.redfin_quiet_score}. Review manually "
                "before relying on either source."
            )
        else:
            result.comparison_note = (
                "HowLoud indicates a calmer location while Redfin "
                f"Quiet is {result.redfin_quiet_score}. Review "
                "manually before relying on either source."
            )

    # Per-source detail is appended as evidence, never as a verdict.
    detail_parts = []
    if traffic_lean == "loud" or (
        observation.traffic_label
        and traffic_lean is None
        and observation.traffic_label.strip().lower() != "calm"
    ):
        detail_parts.append(
            f"traffic reported as {observation.traffic_label}"
        )
    if airport_lean == "loud" or (
        observation.airport_label
        and airport_lean is None
        and observation.airport_label.strip().lower() != "calm"
    ):
        detail_parts.append(
            f"airport noise reported as {observation.airport_label}"
        )
    if detail_parts:
        result.comparison_note += (
            " HowLoud detail: " + ", ".join(detail_parts) + "."
        )

    return result


# -------------------------------------------------------------------
# Enrichment orchestration
# -------------------------------------------------------------------


def enrich_candidate_with_howloud(
    candidate_id: int,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    db_path: Optional[str] = None,
    dry_run: bool = True,
    http_client: Optional[Any] = None,
) -> HowLoudEnrichmentResult:
    """Enrich one candidate with a HowLoud reading.

    Dry-run is the default and performs neither a network call nor any
    database write.

    Args:
        candidate_id: Candidate ID.
        latitude: Latitude supplied by the operator.
        longitude: Longitude supplied by the operator.
        db_path: Path to SQLite database.
        dry_run: When True, preview only.
        http_client: HttpClient to use. Tests pass FakeHttpClient.

    Returns:
        Enrichment result describing what happened.
    """
    path = db_path or config.database_path
    result = HowLoudEnrichmentResult(
        candidate_id=candidate_id,
        dry_run=dry_run,
    )

    request = build_howloud_request_for_candidate(
        candidate_id=candidate_id,
        latitude=latitude,
        longitude=longitude,
        db_path=path,
    )
    result.request = request

    if not request.is_ready:
        result.status = "invalid_request"
        result.errors.extend(request.blocking_reasons)
        result.detail = "Request could not be prepared."
        return result

    if dry_run:
        result.status = "dry_run"
        result.success = True
        result.network_call_performed = False
        result.detail = (
            "Dry run. No request was made and nothing was saved."
        )
        return result

    status = get_howloud_config_status()
    if not status.ready:
        result.status = (
            "missing_api_key"
            if not status.api_key_present
            else "disabled"
        )
        result.errors.extend(status.messages)
        result.detail = "Enrichment is not configured to run."
        return result

    observation = fetch_howloud_noise(
        request,
        http_client=http_client,
        allow_network=True,
    )
    result.network_call_performed = True
    result.observation = observation
    result.status = observation.status

    observation_id = save_howloud_observation(
        observation, db_path=path
    )
    observation.observation_id = observation_id

    if observation.status == "ok":
        result.success = True
        result.detail = (
            f"HowLoud soundscore {observation.noise_score} "
            f"({observation.raw_score_label or 'no label'}) saved as "
            f"observation {observation_id}. Redfin scores unchanged."
        )
    else:
        result.success = False
        result.detail = (
            f"HowLoud request failed with status "
            f"'{observation.status}'. Saved as observation "
            f"{observation_id} for audit."
        )
        if observation.error_message:
            result.errors.append(observation.error_message)

    return result


def list_candidates_needing_howloud(
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List candidates without a successful HowLoud reading.

    Read-only and offline.

    Args:
        db_path: Path to SQLite database.

    Returns:
        One dict per candidate, including whether coordinates are known.
    """
    path = db_path or config.database_path
    if not Path(path).exists():
        return []

    # Read-only: never creates the observations table. When it does
    # not exist yet, every candidate simply needs enrichment.
    has_observations = howloud_table_exists(db_path=path)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        base_query = (
            "SELECT c.candidate_id, c.address, c.city, c.zip, "
            "c.redfin_url, c.quiet_score, c.vibrancy_score, "
            "c.quiet_gatekeeper_result "
            "FROM candidate_review_queue c "
        )
        if has_observations:
            base_query += (
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM howloud_observations h "
                "  WHERE h.candidate_id = c.candidate_id "
                "  AND h.status = 'ok'"
                ") "
            )
        base_query += "ORDER BY c.candidate_id"
        rows = conn.execute(base_query).fetchall()

        needing: List[Dict[str, Any]] = []
        for row in rows:
            coords = None
            if has_observations:
                coords = conn.execute(
                    "SELECT latitude, longitude FROM "
                    "howloud_observations "
                    "WHERE candidate_id = ? "
                    "AND latitude IS NOT NULL "
                    "AND longitude IS NOT NULL "
                    "ORDER BY observation_id DESC LIMIT 1",
                    (row["candidate_id"],),
                ).fetchone()
            needing.append({
                "candidate_id": row["candidate_id"],
                "address": row["address"],
                "city": row["city"],
                "zip": row["zip"],
                "redfin_url": row["redfin_url"],
                "quiet_score": row["quiet_score"],
                "vibrancy_score": row["vibrancy_score"],
                "quiet_gatekeeper_result": row[
                    "quiet_gatekeeper_result"
                ],
                "has_coordinates": coords is not None,
                "latitude": coords["latitude"] if coords else None,
                "longitude": (
                    coords["longitude"] if coords else None
                ),
            })
        return needing
    except sqlite3.Error:
        return []
    finally:
        conn.close()


# -------------------------------------------------------------------
# Report
# -------------------------------------------------------------------


def build_howloud_comparisons(
    db_path: Optional[str] = None,
) -> List[HowLoudComparisonResult]:
    """Build comparisons for every candidate."""
    path = db_path or config.database_path
    if not Path(path).exists():
        return []

    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT candidate_id FROM candidate_review_queue "
            "ORDER BY candidate_id"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    return [
        compare_howloud_to_redfin(r[0], db_path=path) for r in rows
    ]


def export_howloud_noise_report(
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
    fmt: str = "both",
) -> List[str]:
    """Export the HowLoud vs Redfin comparison report.

    Read-only. Contains no API key and no request headers.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Path to exports directory.
        fmt: Export format - csv, md, or both.

    Returns:
        List of exported file paths.
    """
    path = db_path or config.database_path
    out_dir = exports_dir or config.data_exports_dir

    comparisons = build_howloud_comparisons(db_path=path)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"howloud_noise_report_{timestamp}"
    paths: List[str] = []

    if fmt in ("md", "both"):
        md_path = out_path / f"{base}.md"
        md_path.write_text(
            _build_report_md(comparisons, db_path=path),
            encoding="utf-8",
        )
        paths.append(str(md_path))

    if fmt in ("csv", "both"):
        csv_path = out_path / f"{base}.csv"
        csv_path.write_text(
            _build_report_csv(comparisons, db_path=path),
            encoding="utf-8",
        )
        paths.append(str(csv_path))

    return paths


def _observation_status(
    candidate_id: Optional[int],
    db_path: str,
) -> tuple:
    """Return (status, error_message) of the latest observation."""
    if candidate_id is None:
        return ("", "")
    observation = get_latest_howloud_observation(
        candidate_id, db_path=db_path, successful_only=False
    )
    if observation is None:
        return ("none", "")
    return (observation.status, observation.error_message or "")


def _build_report_md(
    comparisons: List[HowLoudComparisonResult],
    db_path: str,
) -> str:
    """Build the HowLoud comparison Markdown report."""
    lines = [
        "# HowLoud Noise Report",
        "",
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Candidates: {len(comparisons)}",
        "",
        "HowLoud is a separate evidence source. Its values are stored "
        "apart from Redfin Quiet/Vibrancy and are never blended into "
        "them. Quiet Score remains the gatekeeper at "
        f"{config.quiet_score_minimum}, and a HowLoud reading never "
        "changes a pass or fail.",
        "",
    ]

    if not comparisons:
        lines.append("No candidates found.")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Comparison")
    lines.append("")
    lines.append(
        "| ID | Address | Redfin Quiet | Redfin Vibrancy | "
        "Gatekeeper | HowLoud Score | HowLoud Label | Traffic | "
        "Airport | Agreement | Manual Review | Status | "
        "Redfin Link |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    )

    for item in comparisons:
        status, _error = _observation_status(
            item.candidate_id, db_path
        )
        link = (
            f"[View]({item.redfin_url})" if item.redfin_url else ""
        )
        lines.append(
            f"| {item.candidate_id} "
            f"| {item.address or ''} "
            f"| {_fmt(item.redfin_quiet_score)} "
            f"| {_fmt(item.redfin_vibrancy_score)} "
            f"| {item.redfin_gatekeeper_result or ''} "
            f"| {_fmt(item.howloud_noise_score)} "
            f"| {item.howloud_score_label or ''} "
            f"| {_fmt(item.howloud_traffic_score)} "
            f"| {_fmt(item.howloud_airport_score)} "
            f"| {item.agreement_level} "
            f"| {'yes' if item.needs_manual_review else 'no'} "
            f"| {status} "
            f"| {link} |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for item in comparisons:
        lines.append(
            f"### Candidate {item.candidate_id} - "
            f"{item.address or ''}"
        )
        lines.append("")
        lines.append(f"- {item.comparison_note}")
        lines.append(f"- {item.gatekeeper_note}")
        if item.howloud_observed_at:
            lines.append(
                f"- HowLoud observed at: {item.howloud_observed_at}"
            )
        lines.append("")

    lines.append("## Safety Note")
    lines.append("")
    lines.append(
        "HowLoud requests are opt-in and run only from an explicit "
        "command. No API key appears in this report. No browser "
        "automation, no Redfin scraping, and no outbound "
        "notifications are involved. This report is analytical "
        "evidence, not a purchase recommendation."
    )
    lines.append("")

    return "\n".join(lines)


def _build_report_csv(
    comparisons: List[HowLoudComparisonResult],
    db_path: str,
) -> str:
    """Build the HowLoud comparison CSV report."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "candidate_id",
        "address",
        "redfin_url",
        "redfin_quiet_score",
        "redfin_vibrancy_score",
        "redfin_gatekeeper_result",
        "howloud_noise_score",
        "howloud_score_label",
        "howloud_traffic_score",
        "howloud_airport_score",
        "howloud_locality_score",
        "agreement_level",
        "needs_manual_review",
        "comparison_note",
        "gatekeeper_note",
        "howloud_observed_at",
        "observation_status",
        "observation_error",
    ])

    for item in comparisons:
        status, error = _observation_status(
            item.candidate_id, db_path
        )
        writer.writerow([
            item.candidate_id,
            item.address or "",
            item.redfin_url or "",
            _fmt(item.redfin_quiet_score),
            _fmt(item.redfin_vibrancy_score),
            item.redfin_gatekeeper_result or "",
            _fmt(item.howloud_noise_score),
            item.howloud_score_label or "",
            _fmt(item.howloud_traffic_score),
            _fmt(item.howloud_airport_score),
            _fmt(item.howloud_locality_score),
            item.agreement_level,
            "yes" if item.needs_manual_review else "no",
            item.comparison_note,
            item.gatekeeper_note,
            item.howloud_observed_at or "",
            status,
            error,
        ])

    return output.getvalue()


def _fmt(value: Optional[float]) -> str:
    """Format an optional number for report output."""
    return "" if value is None else str(value)
