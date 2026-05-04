"""Review queue export utilities."""

from pathlib import Path
from typing import List, Optional

import pandas as pd

from marketsentry.config import config
from marketsentry.database import get_all_candidates
from marketsentry.logging_config import logger
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


def export_candidates_from_db(
    output_file: Optional[str] = None, database_path: Optional[str] = None
) -> str:
    """
    Export all candidates from database to CSV.

    Args:
        output_file: Output CSV file path (defaults to data/exports/review_queue_YYYYMMDD_HHMMSS.csv)
        database_path: Path to database file (uses config default if not specified)

    Returns:
        Path to exported file
    """
    from datetime import datetime

    # Get all candidates from database
    candidates_data = get_all_candidates(database_path)

    if not candidates_data:
        logger.warning("No candidates found in database to export")
        raise ValueError("No candidates found in database")

    # Convert to CandidateProperty objects
    candidates = []
    for data in candidates_data:
        # Convert database row to CandidateProperty
        candidate = CandidateProperty(
            candidate_id=data.get("candidate_id"),
            discovery_date=data["discovery_date"],
            source_site=data["source_site"],
            source_search_url=data["source_search_url"],
            redfin_url=data["redfin_url"],
            address=data["address"],
            normalized_address=data.get("normalized_address"),
            city=data["city"],
            zip=data["zip"],
            price=data.get("price"),
            beds=data.get("beds"),
            baths=data.get("baths"),
            sqft=data.get("sqft"),
            lot_size=data.get("lot_size"),
            displayed_dom=data.get("displayed_dom"),
            quiet_score=data.get("quiet_score"),
            vibrancy_score=data.get("vibrancy_score"),
            quiet_gatekeeper_result=data.get("quiet_gatekeeper_result"),
            garage_spaces=data.get("garage_spaces"),
            gas_service=data.get("gas_service"),
            gas_evidence=data.get("gas_evidence"),
            effective_dom_estimate=data.get("effective_dom_estimate"),
            listing_churn_count=data.get("listing_churn_count"),
            dom_reset_count=data.get("dom_reset_count"),
            sale_rent_alternation_count=data.get("sale_rent_alternation_count"),
            review_status=data.get("review_status", "pending"),
            user_decision=data.get("user_decision"),
            user_notes=data.get("user_notes"),
        )
        candidates.append(candidate)

    # Generate default output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{config.data_exports_dir}/review_queue_{timestamp}.csv"

    # Export to CSV
    output_path = export_review_queue_to_csv(candidates, output_file)
    logger.info(f"Exported {len(candidates)} candidates to {output_path}")

    return output_path
