"""Tests for the complete review workflow."""

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from marketsentry.database import (
    find_candidate_by_address,
    find_candidate_by_url,
    find_watched_by_address,
    get_active_watched_properties,
    get_all_candidates,
    init_db,
    insert_candidate,
    insert_candidates,
    update_candidate_decision,
)
from marketsentry.models import CandidateProperty
from marketsentry.normalization import normalize_address
from marketsentry.review_export import export_candidates_from_db, export_review_queue_to_csv
from marketsentry.review_import import (
    process_review_decisions,
    validate_decision,
)
from marketsentry.sample_data import create_sample_candidates, seed_sample_candidates
from marketsentry.watchlist import (
    calculate_watch_priority,
    promote_candidate_to_watchlist,
)


@pytest.fixture
def temp_db() -> str:
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize database
    init_db(db_path)

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


def test_insert_candidate(temp_db: str) -> None:
    """Test inserting a single candidate."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/123",
        address="123 Test St",
        city="Temecula",
        zip="92592",
        price=750000.0,
        quiet_score=8.5,
        vibrancy_score=2.0,
    )

    candidate_id = insert_candidate(candidate, database_path=temp_db)

    assert candidate_id is not None
    assert candidate_id > 0


def test_insert_candidate_deduplication_by_url(temp_db: str) -> None:
    """Test that candidates are deduplicated by URL."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/123",
        address="123 Test St",
        city="Temecula",
        zip="92592",
    )

    id1 = insert_candidate(candidate, skip_if_exists=True, database_path=temp_db)
    id2 = insert_candidate(candidate, skip_if_exists=True, database_path=temp_db)

    assert id1 == id2


def test_insert_candidate_deduplication_by_address(temp_db: str) -> None:
    """Test that candidates are deduplicated by normalized address."""
    candidate1 = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/123",
        address="123 Main Street",
        city="Temecula",
        zip="92592",
    )

    candidate2 = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/456",  # Different URL
        address="123 Main St",  # Same address, different format
        city="Temecula",
        zip="92592",
    )

    id1 = insert_candidate(candidate1, skip_if_exists=True, database_path=temp_db)
    id2 = insert_candidate(candidate2, skip_if_exists=True, database_path=temp_db)

    assert id1 == id2


def test_insert_multiple_candidates(temp_db: str) -> None:
    """Test inserting multiple candidates."""
    candidates = [
        CandidateProperty(
            discovery_date=date.today(),
            source_site="redfin",
            source_search_url="http://example.com/search",
            redfin_url=f"http://redfin.com/property/{i}",
            address=f"{i} Test St",
            city="Temecula",
            zip="92592",
        )
        for i in range(1, 4)
    ]

    ids = insert_candidates(candidates, database_path=temp_db)

    assert len(ids) == 3
    assert all(id > 0 for id in ids)


def test_find_candidate_by_url(temp_db: str) -> None:
    """Test finding a candidate by URL."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/findme",
        address="123 Find St",
        city="Temecula",
        zip="92592",
    )

    insert_candidate(candidate, database_path=temp_db)

    found = find_candidate_by_url("http://redfin.com/property/findme", temp_db)

    assert found is not None
    assert found["address"] == "123 Find St"


def test_find_candidate_by_address(temp_db: str) -> None:
    """Test finding a candidate by normalized address."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/123",
        address="456 Main Street",
        city="Temecula",
        zip="92592",
    )

    insert_candidate(candidate, database_path=temp_db)

    normalized = normalize_address("456 Main St")  # Different format, same address
    found = find_candidate_by_address(normalized, temp_db)

    assert found is not None


def test_update_candidate_decision(temp_db: str) -> None:
    """Test updating a candidate's decision."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/123",
        address="123 Test St",
        city="Temecula",
        zip="92592",
    )

    candidate_id = insert_candidate(candidate, database_path=temp_db)

    update_candidate_decision(candidate_id, "save", "Great property!", temp_db)

    found = find_candidate_by_url("http://redfin.com/property/123", temp_db)
    assert found["user_decision"] == "save"
    assert found["user_notes"] == "Great property!"
    assert found["review_status"] == "reviewed"


def test_export_review_queue_to_csv(temp_db: str) -> None:
    """Test exporting review queue to CSV."""
    candidates = create_sample_candidates()
    insert_candidates(candidates, database_path=temp_db)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = f"{tmpdir}/review.csv"
        result = export_candidates_from_db(output_file, temp_db)

        assert Path(result).exists()

        # Read and verify CSV
        df = pd.read_csv(result)
        assert len(df) == 3  # Should have 3 sample candidates
        assert "user_decision" in df.columns
        assert "user_notes" in df.columns
        assert "candidate_id" in df.columns


def test_validate_decision() -> None:
    """Test decision validation."""
    assert validate_decision("save") is True
    assert validate_decision("reject") is True
    assert validate_decision("maybe") is True
    assert validate_decision("hold_for_more_data") is True
    assert validate_decision("SAVE") is True  # Case insensitive
    assert validate_decision("invalid") is False
    assert validate_decision("") is False


def test_seed_sample_candidates(temp_db: str) -> None:
    """Test seeding sample candidates."""
    count = seed_sample_candidates(temp_db)

    assert count == 3

    candidates = get_all_candidates(temp_db)
    assert len(candidates) == 3


def test_calculate_watch_priority() -> None:
    """Test watch priority calculation."""
    # High priority: strong quiet + leverage signals
    priority = calculate_watch_priority(9.0, 120, 3, "pass")
    assert priority == 3

    # Medium priority: normal candidate
    priority = calculate_watch_priority(8.0, 30, 0, "pass")
    assert priority == 2

    # Low priority: missing data
    priority = calculate_watch_priority(None, None, None, "fail_no_data")
    assert priority == 1


def test_promote_candidate_to_watchlist(temp_db: str) -> None:
    """Test promoting a candidate to watchlist."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/promote",
        address="789 Promote St",
        city="Temecula",
        zip="92592",
        price=800000.0,
        quiet_score=9.0,
        vibrancy_score=1.5,
        quiet_gatekeeper_result="pass",
        gas_service=True,
        gas_evidence="Gas fireplace",
    )

    candidate_id = insert_candidate(candidate, database_path=temp_db)
    property_id = promote_candidate_to_watchlist(candidate_id, temp_db)

    assert property_id is not None

    # Verify property was created
    normalized = normalize_address("789 Promote St")
    watched = find_watched_by_address(normalized, temp_db)

    assert watched is not None
    assert watched["address"] == "789 Promote St"
    assert watched["gas_service"] == 1  # SQLite stores booleans as integers
    assert watched["gas_evidence"] == "Gas fireplace"


def test_promote_candidate_idempotent(temp_db: str) -> None:
    """Test that promoting a candidate multiple times is idempotent."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/idempotent",
        address="321 Idempotent St",
        city="Temecula",
        zip="92592",
    )

    candidate_id = insert_candidate(candidate, database_path=temp_db)

    property_id1 = promote_candidate_to_watchlist(candidate_id, temp_db)
    property_id2 = promote_candidate_to_watchlist(candidate_id, temp_db)

    assert property_id1 == property_id2

    # Should only have one watched property
    properties = get_active_watched_properties(temp_db)
    assert len(properties) == 1


def test_process_review_decisions(temp_db: str) -> None:
    """Test the full review decision processing workflow."""
    # Seed sample candidates
    seed_sample_candidates(temp_db)

    # Export to CSV
    with tempfile.TemporaryDirectory() as tmpdir:
        export_file = f"{tmpdir}/review.csv"
        export_candidates_from_db(export_file, temp_db)

        # Read CSV and add decisions
        df = pd.read_csv(export_file)
        df.loc[0, "user_decision"] = "save"  # Save first candidate
        df.loc[1, "user_decision"] = "reject"  # Reject second
        df.loc[2, "user_decision"] = "maybe"  # Maybe on third

        # Save modified CSV
        reviewed_file = f"{tmpdir}/reviewed.csv"
        df.to_csv(reviewed_file, index=False)

        # Process decisions
        counts = process_review_decisions(reviewed_file, temp_db)

        assert counts["processed"] == 3
        assert counts["save"] == 1
        assert counts["promoted"] == 1
        assert counts["reject"] == 1
        assert counts["maybe"] == 1

        # Verify watchlist
        properties = get_active_watched_properties(temp_db)
        assert len(properties) == 1


def test_process_review_decisions_validation(temp_db: str) -> None:
    """Test that invalid decisions are caught."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com/search",
        redfin_url="http://redfin.com/property/invalid",
        address="111 Invalid St",
        city="Temecula",
        zip="92592",
    )

    insert_candidate(candidate, database_path=temp_db)

    with tempfile.TemporaryDirectory() as tmpdir:
        export_file = f"{tmpdir}/review.csv"
        export_candidates_from_db(export_file, temp_db)

        # Add invalid decision
        df = pd.read_csv(export_file)
        df.loc[0, "user_decision"] = "invalid_choice"

        reviewed_file = f"{tmpdir}/reviewed.csv"
        df.to_csv(reviewed_file, index=False)

        # Process - should catch invalid decision
        counts = process_review_decisions(reviewed_file, temp_db)

        assert counts["invalid"] == 1
        assert counts["processed"] == 0


def test_non_save_decisions_not_promoted(temp_db: str) -> None:
    """Test that reject/maybe/hold decisions are not promoted."""
    candidates = [
        CandidateProperty(
            discovery_date=date.today(),
            source_site="redfin",
            source_search_url="http://example.com/search",
            redfin_url=f"http://redfin.com/property/{decision}",
            address=f"{i} {decision.title()} St",
            city="Temecula",
            zip="92592",
        )
        for i, decision in enumerate(["reject", "maybe", "hold_for_more_data"], 1)
    ]

    insert_candidates(candidates, database_path=temp_db)

    with tempfile.TemporaryDirectory() as tmpdir:
        export_file = f"{tmpdir}/review.csv"
        export_candidates_from_db(export_file, temp_db)

        df = pd.read_csv(export_file)
        df.loc[0, "user_decision"] = "reject"
        df.loc[1, "user_decision"] = "maybe"
        df.loc[2, "user_decision"] = "hold_for_more_data"

        reviewed_file = f"{tmpdir}/reviewed.csv"
        df.to_csv(reviewed_file, index=False)

        counts = process_review_decisions(reviewed_file, temp_db)

        assert counts["promoted"] == 0

        # Verify no watched properties created
        properties = get_active_watched_properties(temp_db)
        assert len(properties) == 0
