"""Tests for Milestone 10: Effective DOM v2 Operational Integration.

Covers:
- Schema migration adds v2 fields safely
- Migration is idempotent
- persist-effective-dom-v2 updates watched_properties
- persist-effective-dom-v2 preserves user_notes and active_watch_status
- County reset applied persists correctly
- Churn Index persists and is not zeroed by county reset
- snapshot-watchlist captures v2 fields
- Snapshot change detection detects effective_dom_v2 changes
- Snapshot change detection detects recent_churn_index changes
- Monitoring report includes v2 fields
- Candidate analysis report includes v2 fields
- Scoring flags high recent churn neutrally
- Scoring does not let churn override Quiet gatekeeper
- Existing MVP 1-9 tests still pass (verified via full test suite)
"""

import csv
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from marketsentry.database import (
    column_exists,
    execute_insert,
    execute_query,
    execute_update,
    init_db,
    migrate_schema,
)
from marketsentry.models import (
    CandidateProperty,
    ObservationSnapshot,
    SnapshotChangeResult,
    WatchedProperty,
)


class TestSchemaV2Migration:
    """Tests for Milestone 10 schema migrations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        migrate_schema(db_path)
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_migration_adds_v2_columns_to_snapshots(self, temp_db):
        """Schema migration adds v2 fields to property_observation_snapshots."""
        v2_columns = [
            "effective_dom_v1", "effective_dom_v2",
            "effective_dom_delta_v1", "effective_dom_delta_v2",
            "county_reset_applied", "county_reset_date",
            "county_reset_record_type", "county_reset_confidence",
            "recent_churn_index", "recent_churn_lookback_years",
            "recent_churn_event_count", "recent_dom_reset_count",
            "recent_sale_rent_alternation_count", "churn_preserved_after_transfer",
        ]
        for col in v2_columns:
            assert column_exists("property_observation_snapshots", col, temp_db), \
                f"Column {col} missing from property_observation_snapshots"

    def test_migration_adds_v2_columns_to_watched_properties(self, temp_db):
        """Schema migration adds v2 fields to watched_properties."""
        v2_columns = [
            "effective_dom_v1", "effective_dom_v2",
            "effective_dom_delta_v1", "effective_dom_delta_v2",
            "county_reset_applied", "county_reset_date",
            "county_reset_record_type", "county_reset_confidence",
            "recent_churn_index", "recent_churn_lookback_years",
            "recent_churn_event_count", "recent_dom_reset_count",
            "recent_sale_rent_alternation_count", "churn_preserved_after_transfer",
        ]
        for col in v2_columns:
            assert column_exists("watched_properties", col, temp_db), \
                f"Column {col} missing from watched_properties"

    def test_migration_adds_v2_columns_to_candidates(self, temp_db):
        """Schema migration adds v2 fields to candidate_review_queue."""
        v2_columns = [
            "effective_dom_v1", "effective_dom_v2",
            "effective_dom_delta_v1", "effective_dom_delta_v2",
            "county_reset_applied", "county_reset_date",
            "county_reset_record_type", "county_reset_confidence",
            "recent_churn_index", "recent_churn_lookback_years",
            "recent_churn_event_count", "recent_dom_reset_count",
            "recent_sale_rent_alternation_count", "churn_preserved_after_transfer",
        ]
        for col in v2_columns:
            assert column_exists("candidate_review_queue", col, temp_db), \
                f"Column {col} missing from candidate_review_queue"

    def test_migration_is_idempotent(self, temp_db):
        """Running migrate_schema twice does not cause errors."""
        # First migration already ran in fixture; run again
        migrate_schema(temp_db)
        # And again
        migrate_schema(temp_db)
        # Should still have v2 columns
        assert column_exists("watched_properties", "effective_dom_v2", temp_db)
        assert column_exists("property_observation_snapshots", "recent_churn_index", temp_db)
        assert column_exists("candidate_review_queue", "county_reset_applied", temp_db)


class TestPersistEffectiveDomV2:
    """Tests for v2 persistence workflow."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with sample data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        migrate_schema(db_path)
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def _insert_watched_property(self, db_path, **overrides):
        """Insert a watched property and return property_id."""
        defaults = {
            "first_saved_date": "2026-05-01",
            "address": "12345 Test St",
            "normalized_address": "12345 TEST ST",
            "city": "Temecula",
            "zip": "92592",
            "current_price": 750000.0,
            "displayed_dom": 30,
            "effective_dom": 60,
            "effective_dom_delta": 30,
            "quiet_score": 8.5,
            "vibrancy_score": 2.0,
            "garage_spaces": 2,
            "gas_service": 1,
            "active_watch_status": 1,
            "watch_priority": 2,
            "user_notes": "Test property notes",
        }
        defaults.update(overrides)
        cols = ", ".join(defaults.keys())
        placeholders = ", ".join(["?"] * len(defaults))
        query = f"INSERT INTO watched_properties ({cols}) VALUES ({placeholders})"
        return execute_insert(query, tuple(defaults.values()), database_path=db_path)

    def _insert_listing_event(self, db_path, property_id=None, candidate_id=None,
                              event_date="2025-01-15", event_type="listed"):
        """Insert a listing event."""
        query = """
        INSERT INTO listing_events (property_id, candidate_id, event_date, source_site, event_type)
        VALUES (?, ?, ?, ?, ?)
        """
        return execute_insert(
            query, (property_id, candidate_id, event_date, "redfin", event_type),
            database_path=db_path,
        )

    def _insert_candidate(self, db_path, **overrides):
        """Insert a candidate and return candidate_id."""
        defaults = {
            "discovery_date": "2026-05-01",
            "source_site": "redfin",
            "source_search_url": "https://redfin.com/search",
            "redfin_url": "https://redfin.com/CA/Temecula/12345-Test-St/home/1",
            "address": "12345 Test St",
            "normalized_address": "12345 TEST ST",
            "city": "Temecula",
            "zip": "92592",
            "displayed_dom": 30,
            "user_decision": "save",
            "user_notes": "Candidate notes",
        }
        defaults.update(overrides)
        cols = ", ".join(defaults.keys())
        placeholders = ", ".join(["?"] * len(defaults))
        query = f"INSERT INTO candidate_review_queue ({cols}) VALUES ({placeholders})"
        return execute_insert(query, tuple(defaults.values()), database_path=db_path)

    def test_persist_updates_watched_properties(self, temp_db):
        """persist-effective-dom-v2 updates watched_properties with v2 metrics."""
        from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2

        prop_id = self._insert_watched_property(temp_db)
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2025-01-15", event_type="listed")
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2025-06-15", event_type="removed")
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2025-07-01", event_type="listed")

        result = persist_effective_dom_v2(temp_db)

        assert result.properties_scanned >= 1
        assert result.records_updated >= 1

        # Verify v2 fields were written
        rows = execute_query(
            "SELECT effective_dom_v1, effective_dom_v2, recent_churn_index, churn_preserved_after_transfer FROM watched_properties WHERE property_id = ?",
            (prop_id,), database_path=temp_db,
        )
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["effective_dom_v1"] is not None
        assert row["effective_dom_v2"] is not None
        assert row["churn_preserved_after_transfer"] in (1, True)

    def test_persist_preserves_user_notes_and_watch_status(self, temp_db):
        """persist-effective-dom-v2 preserves user_notes and active_watch_status."""
        from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2

        prop_id = self._insert_watched_property(
            temp_db,
            user_notes="Important buyer note",
            watch_priority=3,
            active_watch_status=1,
        )
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2025-01-15", event_type="listed")

        persist_effective_dom_v2(temp_db)

        rows = execute_query(
            "SELECT user_notes, watch_priority, active_watch_status FROM watched_properties WHERE property_id = ?",
            (prop_id,), database_path=temp_db,
        )
        row = dict(rows[0])
        assert row["user_notes"] == "Important buyer note"
        assert row["watch_priority"] == 3
        assert row["active_watch_status"] in (1, True)

    def test_county_reset_applied_persists(self, temp_db):
        """County reset applied flag persists correctly."""
        from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2

        prop_id = self._insert_watched_property(temp_db)
        # Events spanning across a transfer
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2024-01-15", event_type="listed")
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2024-06-15", event_type="removed")
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2025-01-15", event_type="listed")

        # Insert county transfer record between the events
        query = """
        INSERT INTO county_record_observations
            (property_id, source_type, record_date, record_type, normalized_record_type, document_number, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            (prop_id, "recorder", "2024-09-01", "grant_deed", "grant_deed", "2024-DOC-001", "high"),
            database_path=temp_db,
        )

        result = persist_effective_dom_v2(temp_db)

        assert result.county_resets_applied >= 1

        rows = execute_query(
            "SELECT county_reset_applied, county_reset_date, county_reset_record_type FROM watched_properties WHERE property_id = ?",
            (prop_id,), database_path=temp_db,
        )
        row = dict(rows[0])
        assert row["county_reset_applied"] in (1, True)
        assert row["county_reset_date"] is not None
        assert row["county_reset_record_type"] == "grant_deed"

    def test_churn_not_zeroed_by_county_reset(self, temp_db):
        """Churn Index persists and is NOT zeroed by county reset."""
        from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2

        prop_id = self._insert_watched_property(temp_db)
        # Create listing churn events
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2024-01-15", event_type="listed")
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2024-03-15", event_type="removed")
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2024-04-01", event_type="listed")
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2024-07-15", event_type="removed")
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2024-08-01", event_type="listed")
        self._insert_listing_event(temp_db, property_id=prop_id, event_date="2025-01-15", event_type="listed")

        # Insert county transfer
        query = """
        INSERT INTO county_record_observations
            (property_id, source_type, record_date, record_type, normalized_record_type, document_number, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            (prop_id, "recorder", "2024-10-01", "grant_deed", "grant_deed", "2024-DOC-002", "high"),
            database_path=temp_db,
        )

        result = persist_effective_dom_v2(temp_db)

        rows = execute_query(
            "SELECT county_reset_applied, recent_churn_index, churn_preserved_after_transfer FROM watched_properties WHERE property_id = ?",
            (prop_id,), database_path=temp_db,
        )
        row = dict(rows[0])
        # County reset is applied
        assert row["county_reset_applied"] in (1, True)
        # Churn index is NOT zero - churn is preserved
        assert row["recent_churn_index"] is not None
        assert row["recent_churn_index"] > 0, "Churn index should not be zeroed by county reset"
        assert row["churn_preserved_after_transfer"] in (1, True)

    def test_persist_updates_candidates(self, temp_db):
        """persist-effective-dom-v2 updates candidates with listing events."""
        from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2

        cand_id = self._insert_candidate(temp_db)
        self._insert_listing_event(temp_db, candidate_id=cand_id, event_date="2025-01-15", event_type="listed")
        self._insert_listing_event(temp_db, candidate_id=cand_id, event_date="2025-06-15", event_type="price_changed")

        result = persist_effective_dom_v2(temp_db)

        assert result.records_updated >= 1

        rows = execute_query(
            "SELECT effective_dom_v1, effective_dom_v2, user_decision, user_notes FROM candidate_review_queue WHERE candidate_id = ?",
            (cand_id,), database_path=temp_db,
        )
        row = dict(rows[0])
        assert row["effective_dom_v1"] is not None
        assert row["user_decision"] == "save"
        assert row["user_notes"] == "Candidate notes"


class TestSnapshotV2Fields:
    """Tests for v2 fields in watchlist monitoring snapshots."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with v2-persisted data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        migrate_schema(db_path)
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def _insert_watched_with_v2(self, db_path, effective_dom_v2=120, recent_churn_index=3.5,
                                county_reset_applied=0):
        """Insert a watched property with v2 fields populated."""
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, normalized_address, city, zip,
            current_price, displayed_dom, effective_dom, effective_dom_delta,
            quiet_score, vibrancy_score, garage_spaces, gas_service,
            active_watch_status, redfin_url,
            effective_dom_v1, effective_dom_v2, effective_dom_delta_v1,
            effective_dom_delta_v2, county_reset_applied,
            recent_churn_index, recent_churn_lookback_years,
            recent_churn_event_count, churn_preserved_after_transfer
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        return execute_insert(query, (
            "2026-05-01", "12345 Test St", "12345 TEST ST", "Temecula", "92592",
            750000.0, 30, 180, 150,
            8.5, 2.0, 2, 1, 1,
            "https://redfin.com/CA/Temecula/12345-Test-St/home/1",
            180, effective_dom_v2, 150,
            effective_dom_v2 - 30, county_reset_applied,
            recent_churn_index, 3, 5, 1,
        ), database_path=db_path)

    def test_snapshot_captures_v2_fields(self, temp_db):
        """snapshot-watchlist captures v2 fields from watched_properties."""
        from marketsentry.monitoring import create_snapshot_for_property

        prop_id = self._insert_watched_with_v2(temp_db, effective_dom_v2=120, recent_churn_index=4.5)

        result = create_snapshot_for_property(prop_id, temp_db)
        assert result.snapshot_created

        # Read the stored snapshot
        rows = execute_query(
            "SELECT effective_dom_v1, effective_dom_v2, recent_churn_index, churn_preserved_after_transfer "
            "FROM property_observation_snapshots WHERE snapshot_id = ?",
            (result.snapshot_id,), database_path=temp_db,
        )
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["effective_dom_v1"] == 180
        assert row["effective_dom_v2"] == 120
        assert row["recent_churn_index"] == 4.5
        assert row["churn_preserved_after_transfer"] in (1, True)

    def test_change_detection_detects_v2_change(self, temp_db):
        """Change detection detects effective_dom_v2 changes."""
        from marketsentry.monitoring import compare_snapshots

        now = datetime.now()
        prev = ObservationSnapshot(
            property_id=1, snapshot_date=now - timedelta(days=1),
            source_site="redfin", effective_dom_v2=120,
            recent_churn_index=3.0, county_reset_applied=False,
        )
        curr = ObservationSnapshot(
            property_id=1, snapshot_date=now,
            source_site="redfin", effective_dom_v2=90,
            recent_churn_index=3.0, county_reset_applied=False,
        )

        result = compare_snapshots(prev, curr)
        assert result.effective_dom_v2_changed is True
        assert result.has_changes is True
        assert any("Effective DOM v2 changed" in d for d in result.change_details)

    def test_change_detection_detects_churn_change(self, temp_db):
        """Change detection detects recent_churn_index changes."""
        from marketsentry.monitoring import compare_snapshots

        now = datetime.now()
        prev = ObservationSnapshot(
            property_id=1, snapshot_date=now - timedelta(days=1),
            source_site="redfin", effective_dom_v2=120,
            recent_churn_index=3.0, county_reset_applied=False,
        )
        curr = ObservationSnapshot(
            property_id=1, snapshot_date=now,
            source_site="redfin", effective_dom_v2=120,
            recent_churn_index=5.5, county_reset_applied=False,
        )

        result = compare_snapshots(prev, curr)
        assert result.recent_churn_index_changed is True
        assert result.has_changes is True

    def test_change_detection_detects_county_reset_change(self, temp_db):
        """Change detection detects county_reset_applied changes."""
        from marketsentry.monitoring import compare_snapshots

        now = datetime.now()
        prev = ObservationSnapshot(
            property_id=1, snapshot_date=now - timedelta(days=1),
            source_site="redfin", county_reset_applied=False,
        )
        curr = ObservationSnapshot(
            property_id=1, snapshot_date=now,
            source_site="redfin", county_reset_applied=True,
        )

        result = compare_snapshots(prev, curr)
        assert result.county_reset_applied_changed is True
        assert result.has_changes is True


class TestMonitoringReportV2:
    """Tests for v2 fields in watchlist monitoring report."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        migrate_schema(db_path)
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_monitoring_report_includes_v2_fields(self, temp_db):
        """Monitoring report CSV includes v2 columns."""
        from marketsentry.monitoring_report import export_watchlist_monitoring_report

        # Insert a watched property with v2 fields
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, normalized_address, city, zip,
            current_price, active_watch_status, redfin_url,
            effective_dom_v1, effective_dom_v2, effective_dom_delta_v2,
            county_reset_applied, recent_churn_index, churn_preserved_after_transfer
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        execute_insert(query, (
            "2026-05-01", "12345 Test St", "12345 TEST ST", "Temecula", "92592",
            750000.0, 1, "https://redfin.com/CA/Temecula/12345-Test-St/home/1",
            180, 120, 90, 0, 4.5, 1,
        ), database_path=temp_db)

        # Export report
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            output_path = f.name

        row_count = export_watchlist_monitoring_report(output_path, temp_db)
        assert row_count >= 1

        # Read CSV and verify v2 columns present
        with open(output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        v2_cols = [
            "effective_dom_v1", "effective_dom_v2",
            "effective_dom_delta_v1", "effective_dom_delta_v2",
            "county_reset_applied", "county_reset_date",
            "county_reset_record_type", "county_reset_confidence",
            "recent_churn_index", "recent_churn_lookback_years",
            "recent_churn_event_count", "recent_dom_reset_count",
            "recent_sale_rent_alternation_count", "churn_preserved_after_transfer",
            "previous_effective_dom_v2", "effective_dom_v2_change",
            "previous_recent_churn_index", "recent_churn_index_change",
        ]

        for col in v2_cols:
            assert col in fieldnames, f"Missing v2 column: {col}"

        # Verify data
        assert rows[0]["effective_dom_v2"] == "120"
        assert rows[0]["recent_churn_index"] == "4.5"

        Path(output_path).unlink(missing_ok=True)


class TestCandidateReportV2:
    """Tests for v2 fields in candidate analysis report."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        migrate_schema(db_path)
        yield db_path
        import gc
        gc.collect()
        try:
            Path(db_path).unlink(missing_ok=True)
        except PermissionError:
            pass

    def test_candidate_report_includes_v2_fields(self, temp_db):
        """Candidate analysis report includes v2 and churn columns."""
        from marketsentry.candidate_report import export_candidate_analysis_report

        # Insert a candidate
        query = """
        INSERT INTO candidate_review_queue (
            discovery_date, source_site, source_search_url, redfin_url,
            address, city, zip, price, displayed_dom, quiet_score, vibrancy_score,
            garage_spaces, gas_service
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        execute_insert(query, (
            "2026-05-01", "redfin", "https://redfin.com/search",
            "https://redfin.com/CA/Temecula/12345-Test-St/home/1",
            "12345 Test St", "Temecula", "92592", 750000.0, 30, 8.5, 2.0, 2, 1,
        ), database_path=temp_db)

        # Export report
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            output_path = f.name

        csv_path = export_candidate_analysis_report(temp_db, output_path)

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

        v2_cols = [
            "effective_dom_v1", "effective_dom_v2",
            "effective_dom_delta_v1", "effective_dom_delta_v2",
            "county_reset_applied", "county_reset_date",
            "county_reset_record_type",
            "recent_churn_index", "recent_churn_lookback_years",
            "churn_preserved_after_transfer",
            "churn_review_flag", "county_reset_with_churn_flag", "v2_leverage_flag",
        ]

        for col in v2_cols:
            assert col in fieldnames, f"Missing v2 column in candidate report: {col}"

        Path(output_path).unlink(missing_ok=True)


class TestScoringV2Flags:
    """Tests for v2-aware scoring flags."""

    def test_high_churn_flagged_neutrally(self):
        """Scoring flags high recent churn with neutral language."""
        from marketsentry.scoring import score_candidate

        candidate = CandidateProperty(
            address="12345 Test St",
            city="Temecula",
            zip="92592",
            price=750000.0,
            quiet_score=9.0,
            vibrancy_score=1.5,
            displayed_dom=30,
            effective_dom_estimate=180,
            garage_spaces=2,
            gas_service=True,
            redfin_url="https://redfin.com/CA/Temecula/12345-Test-St/home/1",
            recent_churn_index=7.0,
            recent_churn_lookback_years=3,
        )

        score = score_candidate(candidate)

        # Should have churn review flag
        assert score.churn_review_flag is True
        # Should use neutral language
        assert "high_recent_churn" in score.positive_flags
        # Should NOT contain accusatory language
        for flag in score.positive_flags + score.warning_flags:
            assert "spoofing" not in flag.lower()
            assert "manipulation" not in flag.lower()
            assert "fraud" not in flag.lower()
            assert "deception" not in flag.lower()
            assert "bad_actor" not in flag.lower()

    def test_quiet_gatekeeper_overrides_churn(self):
        """Quiet gatekeeper still rejects even with high churn leverage."""
        from marketsentry.scoring import score_candidate

        candidate = CandidateProperty(
            address="12345 Test St",
            city="Temecula",
            zip="92592",
            price=750000.0,
            quiet_score=5.0,  # Below 7.0 threshold
            vibrancy_score=1.5,
            displayed_dom=30,
            effective_dom_estimate=180,
            garage_spaces=2,
            gas_service=True,
            redfin_url="https://redfin.com/CA/Temecula/12345-Test-St/home/1",
            recent_churn_index=9.0,
            recent_dom_reset_count=3,
        )

        score = score_candidate(candidate)

        # Quiet gatekeeper should still reject
        assert score.quiet_gatekeeper_result == "fail_noise_risk"
        assert score.review_recommendation == "reject_location_noise"
        # High churn does NOT override the gatekeeper
        assert "fail_quiet_gatekeeper" in score.warning_flags

    def test_county_reset_with_churn_flag(self):
        """County reset with preserved churn sets the flag."""
        from marketsentry.scoring import score_candidate

        candidate = CandidateProperty(
            address="12345 Test St",
            city="Temecula",
            zip="92592",
            price=750000.0,
            quiet_score=9.0,
            vibrancy_score=1.5,
            displayed_dom=30,
            effective_dom_estimate=50,
            garage_spaces=2,
            gas_service=True,
            redfin_url="https://redfin.com/CA/Temecula/12345-Test-St/home/1",
            county_reset_applied=True,
            recent_churn_index=6.0,
        )

        score = score_candidate(candidate)
        assert score.county_reset_with_churn_flag is True
        assert "county_reset_with_preserved_churn" in score.positive_flags

    def test_v2_leverage_flag_high_delta(self):
        """v2 leverage flag set when effective_dom_delta_v2 >= 90."""
        from marketsentry.scoring import score_candidate

        candidate = CandidateProperty(
            address="12345 Test St",
            city="Temecula",
            zip="92592",
            price=750000.0,
            quiet_score=9.0,
            vibrancy_score=1.5,
            displayed_dom=30,
            effective_dom_estimate=50,
            garage_spaces=2,
            gas_service=True,
            redfin_url="https://redfin.com/CA/Temecula/12345-Test-St/home/1",
            effective_dom_delta_v2=120,
        )

        score = score_candidate(candidate)
        assert score.v2_leverage_flag is True
        assert "high_v2_dom_delta" in score.positive_flags

    def test_no_churn_flag_when_low(self):
        """No churn flag when churn index is low."""
        from marketsentry.scoring import score_candidate

        candidate = CandidateProperty(
            address="12345 Test St",
            city="Temecula",
            zip="92592",
            price=750000.0,
            quiet_score=9.0,
            vibrancy_score=1.5,
            displayed_dom=30,
            garage_spaces=2,
            redfin_url="https://redfin.com/CA/Temecula/12345-Test-St/home/1",
            recent_churn_index=2.0,
        )

        score = score_candidate(candidate)
        assert score.churn_review_flag is False
        assert "high_recent_churn" not in score.positive_flags


class TestSnapshotChangeResultModel:
    """Tests for the updated SnapshotChangeResult model."""

    def test_v2_fields_in_model(self):
        """SnapshotChangeResult has v2 change detection fields."""
        result = SnapshotChangeResult(property_id=1)
        assert hasattr(result, "effective_dom_v2_changed")
        assert hasattr(result, "recent_churn_index_changed")
        assert hasattr(result, "county_reset_applied_changed")
        assert result.effective_dom_v2_changed is False
        assert result.recent_churn_index_changed is False
        assert result.county_reset_applied_changed is False

    def test_observation_snapshot_has_v2_fields(self):
        """ObservationSnapshot has v2 operational fields."""
        snapshot = ObservationSnapshot(
            property_id=1,
            snapshot_date=datetime.now(),
            source_site="redfin",
            effective_dom_v1=180,
            effective_dom_v2=120,
            effective_dom_delta_v2=90,
            county_reset_applied=True,
            recent_churn_index=4.5,
            churn_preserved_after_transfer=True,
        )
        assert snapshot.effective_dom_v1 == 180
        assert snapshot.effective_dom_v2 == 120
        assert snapshot.county_reset_applied is True
        assert snapshot.recent_churn_index == 4.5
        assert snapshot.churn_preserved_after_transfer is True


class TestCandidatePropertyV2Fields:
    """Tests for v2 fields on CandidateProperty model used by scoring."""

    def test_candidate_accepts_v2_fields(self):
        """CandidateProperty model accepts v2 fields via getattr for scoring."""
        candidate = CandidateProperty(
            address="Test",
            city="Test",
            zip="92592",
            redfin_url="https://redfin.com/test",
        )
        # v2 fields exist on the model with sensible defaults
        assert candidate.recent_churn_index is None
        assert candidate.county_reset_applied is False  # default=False
        assert candidate.effective_dom_delta_v2 is None
        assert candidate.churn_preserved_after_transfer is True  # default=True
        assert candidate.recent_churn_lookback_years == 3  # default=3
