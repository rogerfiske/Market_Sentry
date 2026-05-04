"""Review queue export utilities."""

from pathlib import Path
from typing import List

import pandas as pd

from marketsentry.config import config
from marketsentry.models import CandidateProperty


def export_review_queue_to_csv(
    candidates: List[CandidateProperty], output_file: str
) -> str:
    """
    Export candidate review queue to CSV for human review.

    Args:
        candidates: List of candidate properties
        output_file: Output CSV file path

    Returns:
        Path to exported file
    """
    if not candidates:
        raise ValueError("No candidates to export")

    # Convert to dictionaries
    records = [candidate.model_dump() for candidate in candidates]

    # Create DataFrame
    df = pd.DataFrame(records)

    # Add review columns if not present
    if "user_decision" not in df.columns:
        df["user_decision"] = ""
    if "user_notes" not in df.columns:
        df["user_notes"] = ""

    # Reorder columns to put review fields at the end
    review_cols = ["user_decision", "user_notes"]
    other_cols = [col for col in df.columns if col not in review_cols]
    df = df[other_cols + review_cols]

    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export to CSV
    df.to_csv(output_path, index=False)

    return str(output_path)


def export_review_queue_to_excel(
    candidates: List[CandidateProperty], output_file: str
) -> str:
    """
    Export candidate review queue to Excel for human review.

    Args:
        candidates: List of candidate properties
        output_file: Output Excel file path

    Returns:
        Path to exported file
    """
    if not candidates:
        raise ValueError("No candidates to export")

    # Convert to dictionaries
    records = [candidate.model_dump() for candidate in candidates]

    # Create DataFrame
    df = pd.DataFrame(records)

    # Add review columns if not present
    if "user_decision" not in df.columns:
        df["user_decision"] = ""
    if "user_notes" not in df.columns:
        df["user_notes"] = ""

    # Reorder columns
    review_cols = ["user_decision", "user_notes"]
    other_cols = [col for col in df.columns if col not in review_cols]
    df = df[other_cols + review_cols]

    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export to Excel
    df.to_excel(output_path, index=False, engine="openpyxl")

    return str(output_path)
