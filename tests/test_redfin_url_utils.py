"""Tests for Redfin URL utilities."""

import pytest

from marketsentry.redfin_url_utils import (
    extract_address_from_redfin_url,
    extract_city_from_redfin_url,
    extract_redfin_home_id,
    extract_zip_from_redfin_url,
    is_redfin_url,
    normalize_redfin_url,
)


class TestIsRedfinUrl:
    """Tests for is_redfin_url function."""

    def test_valid_redfin_property_url(self):
        """Test valid Redfin property URL."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        assert is_redfin_url(url) is True

    def test_valid_redfin_url_without_www(self):
        """Test valid Redfin URL without www."""
        url = "https://redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        assert is_redfin_url(url) is True

    def test_valid_redfin_url_http(self):
        """Test valid Redfin URL with http."""
        url = "http://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        assert is_redfin_url(url) is True

    def test_invalid_non_property_url(self):
        """Test invalid non-property Redfin URL."""
        url = "https://www.redfin.com/city/19701/CA/Temecula"
        assert is_redfin_url(url) is False

    def test_invalid_non_redfin_url(self):
        """Test invalid non-Redfin URL."""
        url = "https://www.zillow.com/homedetails/12345-Main-St/123456_zpid/"
        assert is_redfin_url(url) is False

    def test_invalid_empty_url(self):
        """Test empty URL."""
        assert is_redfin_url("") is False

    def test_invalid_none_url(self):
        """Test None URL."""
        assert is_redfin_url(None) is False


class TestNormalizeRedfinUrl:
    """Tests for normalize_redfin_url function."""

    def test_normalize_removes_query_params(self):
        """Test normalization removes query parameters."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263?utm_source=test"
        normalized = normalize_redfin_url(url)
        assert "?" not in normalized
        assert "utm_source" not in normalized

    def test_normalize_removes_fragment(self):
        """Test normalization removes fragment."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263#details"
        normalized = normalize_redfin_url(url)
        assert "#" not in normalized

    def test_normalize_removes_trailing_slash(self):
        """Test normalization removes trailing slash."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263/"
        normalized = normalize_redfin_url(url)
        assert not normalized.endswith("/")

    def test_normalize_ensures_https(self):
        """Test normalization ensures https."""
        url = "http://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        normalized = normalize_redfin_url(url)
        assert normalized.startswith("https://")

    def test_normalize_ensures_www(self):
        """Test normalization ensures www subdomain."""
        url = "https://redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        normalized = normalize_redfin_url(url)
        assert "www.redfin.com" in normalized

    def test_normalize_invalid_url_returns_none(self):
        """Test normalization of invalid URL returns None."""
        url = "https://www.zillow.com/homedetails/12345-Main-St/123456_zpid/"
        assert normalize_redfin_url(url) is None

    def test_normalize_empty_url_returns_none(self):
        """Test normalization of empty URL returns None."""
        assert normalize_redfin_url("") is None


class TestExtractRedfinHomeId:
    """Tests for extract_redfin_home_id function."""

    def test_extract_home_id(self):
        """Test extracting home ID from valid URL."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        home_id = extract_redfin_home_id(url)
        assert home_id == "6574263"

    def test_extract_home_id_with_params(self):
        """Test extracting home ID with query params."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263?utm_source=test"
        home_id = extract_redfin_home_id(url)
        assert home_id == "6574263"

    def test_extract_home_id_invalid_url(self):
        """Test extracting home ID from invalid URL."""
        url = "https://www.redfin.com/city/19701/CA/Temecula"
        assert extract_redfin_home_id(url) is None

    def test_extract_home_id_empty_url(self):
        """Test extracting home ID from empty URL."""
        assert extract_redfin_home_id("") is None


class TestExtractAddressFromRedfinUrl:
    """Tests for extract_address_from_redfin_url function."""

    def test_extract_address(self):
        """Test extracting address from valid URL."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        address = extract_address_from_redfin_url(url)
        assert address == "46197 Via La Tranquila 92592"

    def test_extract_address_with_hyphenated_name(self):
        """Test extracting address with hyphenated street name."""
        url = "https://www.redfin.com/CA/Temecula/43511-Calle-Nacido-92592/home/6199187"
        address = extract_address_from_redfin_url(url)
        assert address == "43511 Calle Nacido 92592"

    def test_extract_address_invalid_url(self):
        """Test extracting address from invalid URL."""
        url = "https://www.redfin.com/city/19701/CA/Temecula"
        assert extract_address_from_redfin_url(url) is None

    def test_extract_address_empty_url(self):
        """Test extracting address from empty URL."""
        assert extract_address_from_redfin_url("") is None


class TestExtractCityFromRedfinUrl:
    """Tests for extract_city_from_redfin_url function."""

    def test_extract_city(self):
        """Test extracting city from valid URL."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        city = extract_city_from_redfin_url(url)
        assert city == "Temecula"

    def test_extract_city_murrieta(self):
        """Test extracting Murrieta city."""
        url = "https://www.redfin.com/CA/Murrieta/25678-Via-Viejo-92563/home/7123456"
        city = extract_city_from_redfin_url(url)
        assert city == "Murrieta"

    def test_extract_city_invalid_url(self):
        """Test extracting city from invalid URL."""
        url = "https://www.redfin.com/city/19701"
        assert extract_city_from_redfin_url(url) is None


class TestExtractZipFromRedfinUrl:
    """Tests for extract_zip_from_redfin_url function."""

    def test_extract_zip(self):
        """Test extracting ZIP from valid URL."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        zip_code = extract_zip_from_redfin_url(url)
        assert zip_code == "92592"

    def test_extract_zip_different_code(self):
        """Test extracting different ZIP code."""
        url = "https://www.redfin.com/CA/Murrieta/25678-Via-Viejo-92563/home/7123456"
        zip_code = extract_zip_from_redfin_url(url)
        assert zip_code == "92563"

    def test_extract_zip_invalid_url(self):
        """Test extracting ZIP from invalid URL."""
        url = "https://www.redfin.com/city/19701/CA/Temecula"
        assert extract_zip_from_redfin_url(url) is None
