"""Tests for Redfin HTML fixture parser."""

import tempfile
from pathlib import Path

import pytest

from marketsentry.database import get_all_candidates, get_table_count, init_db
from marketsentry.redfin_fixture_parser import (
    parse_redfin_fixtures_from_directory,
    parse_redfin_html_fixture,
)


@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    init_db(db_path)
    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


class TestParseRedfinHtmlFixture:
    """Tests for parse_redfin_html_fixture function."""

    def test_parse_valid_fixture(self):
        """Test parsing a valid HTML fixture."""
        fixture_path = "tests/fixtures/redfin_search_fixture.html"

        result = parse_redfin_html_fixture(fixture_path)

        assert result.parse_status in ["success", "partial"]
        assert result.candidates_found == 3
        assert len(result.candidates) == 3

        # Check that URLs were extracted and normalized
        urls = [c.redfin_url for c in result.candidates]
        assert any("46197-Via-La-Tranquila" in url for url in urls)
        assert any("43511-Calle-Nacido" in url for url in urls)
        assert any("25678-Via-Viejo" in url for url in urls)

        # All URLs should be normalized (https, www)
        for url in urls:
            assert url.startswith("https://www.redfin.com")

    def test_parse_extracts_address_data(self):
        """Test that parser extracts address data from URLs."""
        fixture_path = "tests/fixtures/redfin_search_fixture.html"

        result = parse_redfin_html_fixture(fixture_path)

        # Check first candidate
        candidate = result.candidates[0]
        assert candidate.address is not None
        assert candidate.city in ["Temecula", "Murrieta"]
        assert candidate.zip in ["92592", "92563"]

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file."""
        result = parse_redfin_html_fixture("nonexistent.html")

        assert result.parse_status == "failed"
        assert "not found" in result.errors[0].lower()

    def test_parse_empty_fixture(self):
        """Test parsing fixture with no property URLs."""
        # Create a temporary HTML file with no property links
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as f:
            f.write("<html><body><p>No properties here</p></body></html>")
            html_path = f.name

        try:
            result = parse_redfin_html_fixture(html_path)

            assert result.parse_status in ["partial", "failed"]
            assert result.candidates_found == 0
            assert len(result.warnings) > 0 or len(result.errors) > 0

        finally:
            Path(html_path).unlink(missing_ok=True)

    def test_parse_handles_relative_urls(self):
        """Test that parser handles relative URLs correctly."""
        fixture_path = "tests/fixtures/redfin_search_fixture.html"

        result = parse_redfin_html_fixture(fixture_path)

        # The fixture contains a relative URL: /CA/Murrieta/25678-Via-Viejo-92563/home/7123456
        # It should be converted to absolute URL
        urls = [c.redfin_url for c in result.candidates]
        murrieta_url = next(url for url in urls if "Murrieta" in url)
        assert murrieta_url.startswith("https://www.redfin.com")


class TestParseRedfinFixturesFromDirectory:
    """Tests for parse_redfin_fixtures_from_directory function."""

    def test_parse_directory(self, temp_db):
        """Test parsing all fixtures in a directory."""
        fixtures_dir = "tests/fixtures"

        result = parse_redfin_fixtures_from_directory(fixtures_dir, temp_db)

        # Should find and process the HTML fixture
        assert result.total_rows_read >= 1
        assert result.candidates_inserted >= 3

        # Verify candidates were inserted
        candidates = get_all_candidates(temp_db)
        assert len(candidates) >= 3

    def test_parse_directory_inserts_candidates(self, temp_db):
        """Test that parsing inserts candidates into database."""
        fixtures_dir = "tests/fixtures"

        parse_redfin_fixtures_from_directory(fixtures_dir, temp_db)

        candidates = get_all_candidates(temp_db)

        # Verify candidate details
        assert len(candidates) >= 3

        # Check that candidates have required fields
        for candidate in candidates:
            assert candidate["redfin_url"]
            assert candidate["source_site"] == "redfin"
            assert candidate["address"]
            assert candidate["city"]
            assert candidate["zip"]

    def test_parse_directory_records_source_pages(self, temp_db):
        """Test that parsing records source page audit entries."""
        fixtures_dir = "tests/fixtures"

        parse_redfin_fixtures_from_directory(fixtures_dir, temp_db)

        # Check source_pages table
        source_pages_count = get_table_count("source_pages", temp_db)
        assert source_pages_count >= 3

    def test_parse_directory_deduplicates(self, temp_db):
        """Test that re-parsing doesn't create duplicates."""
        fixtures_dir = "tests/fixtures"

        # First parse
        result1 = parse_redfin_fixtures_from_directory(fixtures_dir, temp_db)
        first_count = len(get_all_candidates(temp_db))

        # Second parse (should skip duplicates)
        result2 = parse_redfin_fixtures_from_directory(fixtures_dir, temp_db)
        second_count = len(get_all_candidates(temp_db))

        # Count should not increase
        assert first_count == second_count

    def test_parse_nonexistent_directory(self, temp_db):
        """Test parsing nonexistent directory."""
        with pytest.raises(FileNotFoundError):
            parse_redfin_fixtures_from_directory("nonexistent_dir", temp_db)

    def test_parse_empty_directory(self, temp_db):
        """Test parsing directory with no HTML files."""
        # Create temporary empty directory
        with tempfile.TemporaryDirectory() as temp_dir:
            result = parse_redfin_fixtures_from_directory(temp_dir, temp_db)

            assert result.total_rows_read == 0
            assert result.candidates_inserted == 0
            assert "No HTML files" in (result.notes or "")

    def test_parse_directory_not_a_directory(self, temp_db):
        """Test parsing when path is not a directory."""
        # Use a file path instead of directory
        file_path = "tests/fixtures/redfin_search_fixture.html"

        with pytest.raises(ValueError, match="Not a directory"):
            parse_redfin_fixtures_from_directory(file_path, temp_db)
