"""Review decision import utilities."""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from marketsentry.database import record_review_action, update_candidate_decision
from marketsentry.logging_config import logger
from marketsentry.models import ReviewDecision
from marketsentry.watchlist import promote_candidate_to_watchlist


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

# Valid user decision values
VALID_DECISIONS = {"save", "reject", "maybe", "hold_for_more_data"}


def validate_decision(decision: str) -> bool:
    """
    Validate a user decision value.

    Args:
        decision: User decision string

    Returns:
        True if valid, False otherwise
    """
    return decision.lower() in VALID_DECISIONS


def process_review_decisions(
    input_file: str, database_path: Optional[str] = None
) -> Dict[str, int]:
    """
    Process review decisions from CSV file.

    Reads the CSV, validates decisions, updates the database,
    and promotes 'save' decisions to the watchlist.

    Args:
        input_file: Path to CSV file with review decisions
        database_path: Path to database file

    Returns:
        Dict with counts of processed, saved, rejected, maybe, etc.
    """
    # Import decisions from CSV
    decisions = import_review_decisions_from_csv(input_file)

    if not decisions:
        logger.warning("No decisions found in CSV file")
        return {
            "total": 0,
            "processed": 0,
            "save": 0,
            "promoted": 0,
            "reject": 0,
            "maybe": 0,
            "hold_for_more_data": 0,
            "invalid": 0,
            "errors": 0,
        }

    counts = {
        "total": len(decisions),
        "processed": 0,
        "save": 0,
        "promoted": 0,
        "reject": 0,
        "maybe": 0,
        "hold_for_more_data": 0,
        "invalid": 0,
        "errors": 0,
    }

    for decision in decisions:
        try:
            # Validate decision
            if not validate_decision(decision.user_decision):
                logger.warning(
                    f"Invalid decision for candidate {decision.candidate_id}: {decision.user_decision}"
                )
                counts["invalid"] += 1
                continue

            decision_lower = decision.user_decision.lower()

            # Update candidate with decision
            update_candidate_decision(
                decision.candidate_id,
                decision_lower,
                decision.user_notes,
                database_path,
            )

            counts["processed"] += 1
            counts[decision_lower] += 1

            # Promote to watchlist if decision is 'save'
            if decision_lower == "save":
                property_id = promote_candidate_to_watchlist(
                    decision.candidate_id, database_path
                )
                if property_id:
                    counts["promoted"] += 1

                    # Record review action
                    record_review_action(
                        decision.candidate_id,
                        decision_lower,
                        decision.user_notes,
                        property_id,
                        database_path,
                    )
                else:
                    logger.warning(
                        f"Failed to promote candidate {decision.candidate_id} to watchlist"
                    )

            else:
                # Record review action for non-save decisions
                record_review_action(
                    decision.candidate_id,
                    decision_lower,
                    decision.user_notes,
                    None,
                    database_path,
                )

        except Exception as e:
            logger.error(
                f"Error processing decision for candidate {decision.candidate_id}: {e}"
            )
            counts["errors"] += 1

    logger.info(
        f"Processed {counts['processed']}/{counts['total']} decisions: "
        f"{counts['save']} saved ({counts['promoted']} promoted), "
        f"{counts['reject']} rejected, {counts['maybe']} maybe, "
        f"{counts['hold_for_more_data']} hold, "
        f"{counts['invalid']} invalid, {counts['errors']} errors"
    )

    return counts
