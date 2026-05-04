"""Review decision import utilities."""

from pathlib import Path
from typing import List

import pandas as pd

from marketsentry.models import ReviewDecision


def import_review_decisions_from_csv(input_file: str) -> List[ReviewDecision]:
    """
    Import user review decisions from CSV.

    Args:
        input_file: Input CSV file path

    Returns:
        List of review decisions
    """
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Read CSV
    df = pd.read_csv(input_path)

    # Validate required columns
    required_cols = ["candidate_id", "user_decision"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Required column missing: {col}")

    # Filter rows with decisions
    df = df[df["user_decision"].notna() & (df["user_decision"] != "")]

    # Convert to ReviewDecision objects
    decisions = []
    for _, row in df.iterrows():
        decision = ReviewDecision(
            candidate_id=int(row["candidate_id"]),
            user_decision=str(row["user_decision"]),
            user_notes=str(row.get("user_notes", "")) if pd.notna(row.get("user_notes")) else None,
        )
        decisions.append(decision)

    return decisions


def import_review_decisions_from_excel(input_file: str) -> List[ReviewDecision]:
    """
    Import user review decisions from Excel.

    Args:
        input_file: Input Excel file path

    Returns:
        List of review decisions
    """
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Read Excel
    df = pd.read_excel(input_path, engine="openpyxl")

    # Validate required columns
    required_cols = ["candidate_id", "user_decision"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Required column missing: {col}")

    # Filter rows with decisions
    df = df[df["user_decision"].notna() & (df["user_decision"] != "")]

    # Convert to ReviewDecision objects
    decisions = []
    for _, row in df.iterrows():
        decision = ReviewDecision(
            candidate_id=int(row["candidate_id"]),
            user_decision=str(row["user_decision"]),
            user_notes=str(row.get("user_notes", "")) if pd.notna(row.get("user_notes")) else None,
        )
        decisions.append(decision)

    return decisions
