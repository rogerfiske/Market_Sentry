"""Tests for gas detection functionality."""

import pytest

from marketsentry.gas_detection import detect_gas_service, extract_gas_evidence


def test_detect_gas_service_fireplace() -> None:
    """Test gas detection with fireplace mention."""
    text = "Beautiful home with gas fireplace and hardwood floors."
    has_gas, evidence = detect_gas_service(text)

    assert has_gas is True
    assert evidence is not None
    assert "gas fireplace" in evidence.lower()


def test_detect_gas_service_multiple() -> None:
    """Test gas detection with multiple gas features."""
    text = "Features include gas range, gas heating, and gas fireplace."
    has_gas, evidence = detect_gas_service(text)

    assert has_gas is True
    assert evidence is not None


def test_detect_gas_service_no_gas() -> None:
    """Test gas detection when no gas mentioned."""
    text = "Electric range, electric heating, beautiful tile floors."
    has_gas, evidence = detect_gas_service(text)

    assert has_gas is False
    assert evidence is None


def test_detect_gas_service_none_input() -> None:
    """Test gas detection with None input."""
    has_gas, evidence = detect_gas_service(None)

    assert has_gas is False
    assert evidence is None


def test_detect_gas_service_empty_string() -> None:
    """Test gas detection with empty string."""
    has_gas, evidence = detect_gas_service("")

    assert has_gas is False
    assert evidence is None


def test_detect_gas_service_case_insensitive() -> None:
    """Test gas detection is case insensitive."""
    text = "GAS RANGE and GAS OVEN included."
    has_gas, evidence = detect_gas_service(text)

    assert has_gas is True
    assert evidence is not None


def test_extract_gas_evidence() -> None:
    """Test extracting gas evidence."""
    text = "Kitchen has gas cooktop and gas oven."
    evidence = extract_gas_evidence(text)

    assert evidence is not None
    assert "gas" in evidence.lower()


def test_extract_gas_evidence_none() -> None:
    """Test extracting gas evidence when none exists."""
    text = "All electric appliances."
    evidence = extract_gas_evidence(text)

    assert evidence is None
