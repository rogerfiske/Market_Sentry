"""Tests for Redfin URL import from CSV."""

import tempfile
from pathlib import Path

import pytest

from marketsentry.database import (
    get_all_candidates,
    get_table_count,
    init_db,
    update_candidate_decision,
)
from marketsentry.redfin_url_import import import_redfin_urls_from_csv


@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    init_db(db_path)
    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


class TestImportRedfinUrlsFromCsv:
    """Tests for import_redfin_urls_from_csv function."""

    def test_import_valid_urls(self, temp_db):
        """Test importing valid Redfin URLs from CSV."""
        csv_path = "tests/fixtures/redfin_urls_valid.csv"

        result = import_redfin_urls_from_csv(csv_path, temp_db)

        assert result.total_rows_read == 3
        assert result.candidates_inserted == 3
        assert result.candidates_skipped == 0
        assert result.rows_rejected == 0

        # Verify candidates were inserted
        candidates = get_all_candidates(temp_db)
        assert len(candidates) == 3

        # Check first candidate details
        candidate = candidates[0]
        assert "redfin.com" in candidate["redfin_url"]
        assert candidate["source_site"] == "redfin"
        assert candidate["city"] in ["Temecula", "Murrieta"]

    def test_import_mixed_valid_invalid(self, temp_db):
        """Test importing CSV with mixed valid and invalid URLs."""
        csv_path = "tests/fixtures/redfin_urls_mixed_invalid.csv"

        result = import_redfin_urls_from_csv(csv_path, temp_db)

        assert result.total_rows_read == 5
        # Should have 2 valid URLs
        assert result.candidates_inserted == 2
        # Should reject 3 rows (Zillow URL, empty URL, non-property URL)
        assert result.rows_rejected == 3
        assert result.parse_warnings >= 3

    def test_import_duplicate_urls(self, temp_db):
        """Test importing duplicate URLs."""
        csv_path = "tests/fixtures/redfin_urls_valid.csv"

        # First import
        result1 = import_redfin_urls_from_csv(csv_path, temp_db)
        assert result1.candidates_inserted == 3

        # Second import (should skip duplicates)
        result2 = import_redfin_urls_from_csv(csv_path, temp_db)
        # Note: Current implementation returns existing IDs as "inserted"
        # so we check that total candidates hasn't increased
        candidates = get_all_candidates(temp_db)
        assert len(candidates) == 3

    def test_import_preserves_user_decision(self, temp_db):
        """Test that re-importing doesn't overwrite user decisions."""
        csv_path = "tests/fixtures/redfin_urls_valid.csv"

        # First import
        import_redfin_urls_from_csv(csv_path, temp_db)

        # Update a candidate's decision
        candidates = get_all_candidates(temp_db)
        candidate_id = candidates[0]["candidate_id"]
        update_candidate_decision(candidate_id, "save", "Test note", temp_db)

        # Re-import
        import_redfin_urls_from_csv(csv_path, temp_db)

        # Verify decision was preserved
        updated_candidates = get_all_candidates(temp_db)
        updated_candidate = next(
            c for c in updated_candidates if c["candidate_id"] == candidate_id
        )
        assert updated_candidate["user_decision"] == "save"
        assert updated_candidate["user_notes"] == "Test note"

    def test_import_nonexistent_file(self, temp_db):
        """Test importing from nonexistent file."""
        with pytest.raises(FileNotFoundError):
            import_redfin_urls_from_csv("nonexistent.csv", temp_db)

    def test_import_missing_redfin_url_column(self, temp_db):
        """Test importing CSV without required redfin_url column."""
        # Create a temporary CSV without redfin_url column
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("address,city,zip\n")
            f.write("123 Main St,Temecula,92592\n")
            csv_path = f.name

        try:
            with pytest.raises(ValueError, match="must contain 'redfin_url' column"):
                import_redfin_urls_from_csv(csv_path, temp_db)
        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_import_extracts_data_from_url(self, temp_db):
        """Test that import extracts address, city, ZIP from URL when not provided."""
        # Create a temporary CSV with URL but no address data
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("redfin_url\n")
            f.write(
                "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263\n"
            )
            csv_path = f.name

        try:
            result = import_redfin_urls_from_csv(csv_path, temp_db)

            assert result.candidates_inserted == 1

            candidates = get_all_candidates(temp_db)
            candidate = candidates[0]

            # Verify extracted data
            assert "46197 Via La Tranquila" in candidate["address"]
            assert candidate["city"] == "Temecula"
            assert candidate["zip"] == "92592"

        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_import_normalizes_urls(self, temp_db):
        """Test that import normalizes URLs."""
        # Create a temporary CSV with unnormalized URL
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("redfin_url\n")
            f.write(
                "http://redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263/?utm_source=test\n"
            )
            csv_path = f.name

        try:
            import_redfin_urls_from_csv(csv_path, temp_db)

            candidates = get_all_candidates(temp_db)
            candidate = candidates[0]

            # Verify normalization
            assert candidate["redfin_url"].startswith("https://www.redfin.com")
            assert "?" not in candidate["redfin_url"]
            assert not candidate["redfin_url"].endswith("/")

        finally:
            Path(csv_path).unlink(missing_ok=True)
