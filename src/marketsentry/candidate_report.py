"""Candidate analysis report generation."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from marketsentry.config import config
from marketsentry.database import get_connection
from marketsentry.effective_dom import calculate_all_effective_dom_metrics
from marketsentry.models import CandidateProperty, ListingEvent
from marketsentry.scoring import score_candidate


def export_candidate_analysis_report(
    database_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Export candidate analysis report to CSV.

    Args:
        database_path: Path to database (defaults to config)
        output_path: Output file path (defaults to timestamped file in data/exports/)

    Returns:
        Path to exported file
    """
    database_path = database_path or config.database_path

    # Generate output path if not provided
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"candidate_analysis_{timestamp}.csv"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load candidates from database
    candidates = _load_candidates_with_metrics(database_path)

    # Write CSV report
    _write_csv_report(candidates, output_path)

    return str(output_path)


def _load_candidates_with_metrics(database_path: str) -> List[dict]:
    """
    Load candidates with calculated metrics and scoring.

    Args:
        database_path: Path to database

    Returns:
        List of candidate dictionaries with all report fields
    """
    conn = get_connection(database_path)
    cursor = conn.cursor()

    # Load all candidates
    cursor.execute("""
        SELECT
            candidate_id,
            redfin_url,
            address,
            city,
            zip,
            price,
            beds,
            baths,
            sqft,
            displayed_dom,
            quiet_score,
            vibrancy_score,
            quiet_gatekeeper_result,
            garage_spaces,
            gas_service,
            gas_evidence,
            effective_dom_estimate,
            listing_churn_count,
            dom_reset_count,
            sale_rent_alternation_count,
            user_decision,
            user_notes
        FROM candidate_review_queue
        ORDER BY candidate_id
    """)

    rows = cursor.fetchall()
    candidates = []

    for row in rows:
        candidate_id = row[0]

        # Create candidate object
        candidate = CandidateProperty(
            candidate_id=candidate_id,
            redfin_url=row[1],
            address=row[2],
            city=row[3],
            zip=row[4],
            price=row[5],
            beds=row[6],
            baths=row[7],
            sqft=row[8],
            displayed_dom=row[9],
            quiet_score=row[10],
            vibrancy_score=row[11],
            quiet_gatekeeper_result=row[12],
            garage_spaces=row[13],
            gas_service=row[14],
            gas_evidence=row[15],
            effective_dom_estimate=row[16],
            listing_churn_count=row[17],
            dom_reset_count=row[18],
            sale_rent_alternation_count=row[19],
            user_decision=row[20],
            user_notes=row[21],
        )

        # Load listing events for this candidate
        cursor.execute("""
            SELECT
                event_date,
                source_site,
                event_type,
                new_value,
                mls_number
            FROM listing_events
            WHERE candidate_id = ?
            ORDER BY event_date
        """, (candidate_id,))

        event_rows = cursor.fetchall()
        listing_events = []
        for row in event_rows:
            # Try to parse price from new_value (may be None or non-numeric)
            price_value = None
            if row[3]:
                try:
                    price_value = float(row[3])
                except (ValueError, TypeError):
                    pass

            listing_events.append(
                ListingEvent(
                    event_date=row[0],
                    source_site=row[1] or "redfin",
                    event_type=row[2] or "unknown",
                    price=price_value,
                    source_mls=row[4],  # Using mls_number as source_mls
                )
            )

        # Calculate effective DOM metrics
        metrics = calculate_all_effective_dom_metrics(
            listing_events,
            displayed_dom=candidate.displayed_dom,
        )

        # Score the candidate
        score = score_candidate(candidate)

        # Build report dictionary
        candidates.append({
            "candidate_id": candidate_id,
            "review_recommendation": score.review_recommendation,
            "overall_review_score": f"{score.overall_review_score:.1f}" if score.overall_review_score is not None else "",
            "location_fit_label": score.location_fit_label or "",
            "quiet_gatekeeper_result": score.quiet_gatekeeper_result or "",
            "quiet_score": f"{candidate.quiet_score:.1f}" if candidate.quiet_score is not None else "",
            "vibrancy_score": f"{candidate.vibrancy_score:.1f}" if candidate.vibrancy_score is not None else "",
            "price": f"${candidate.price:,.0f}" if candidate.price is not None else "",
            "beds": candidate.beds or "",
            "baths": candidate.baths or "",
            "sqft": f"{candidate.sqft:,}" if candidate.sqft else "",
            "garage_spaces": candidate.garage_spaces or "",
            "gas_service": "Yes" if candidate.gas_service is True else ("No" if candidate.gas_service is False else ""),
            "gas_evidence": (candidate.gas_evidence[:50] + "..." if candidate.gas_evidence and len(candidate.gas_evidence) > 50 else candidate.gas_evidence or ""),
            "displayed_dom": metrics.displayed_dom or "",
            "effective_dom": metrics.effective_dom or "",
            "effective_dom_delta": metrics.effective_dom_delta or "",
            "listing_churn_count": metrics.listing_churn_count,
            "dom_reset_count": metrics.dom_reset_count,
            "sale_rent_alternation_count": metrics.sale_rent_alternation_count,
            "price_change_count": metrics.price_change_count,
            "data_confidence_score": f"{score.data_confidence_score:.1f}" if score.data_confidence_score is not None else "",
            "warning_flags": "; ".join(score.warning_flags) if score.warning_flags else "",
            "positive_flags": "; ".join(score.positive_flags) if score.positive_flags else "",
            "address": candidate.address or "",
            "city": candidate.city or "",
            "zip": candidate.zip or "",
            "redfin_url": candidate.redfin_url or "",
            "user_decision": candidate.user_decision or "",
            "user_notes": candidate.user_notes or "",
        })

    conn.close()
    return candidates


def _write_csv_report(candidates: List[dict], output_path: Path):
    """
    Write candidate analysis report to CSV.

    Args:
        candidates: List of candidate dictionaries
        output_path: Output file path
    """
    # Define report columns in order
    columns = [
        "candidate_id",
        "review_recommendation",
        "overall_review_score",
        "location_fit_label",
        "quiet_gatekeeper_result",
        "quiet_score",
        "vibrancy_score",
        "price",
        "beds",
        "baths",
        "sqft",
        "garage_spaces",
        "gas_service",
        "gas_evidence",
        "displayed_dom",
        "effective_dom",
        "effective_dom_delta",
        "listing_churn_count",
        "dom_reset_count",
        "sale_rent_alternation_count",
        "price_change_count",
        "data_confidence_score",
        "warning_flags",
        "positive_flags",
        "address",
        "city",
        "zip",
        "redfin_url",
        "user_decision",
        "user_notes",
    ]

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()
        writer.writerows(candidates)


def export_markdown_summary(
    database_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Export candidate analysis summary to Markdown.

    Args:
        database_path: Path to database (defaults to config)
        output_path: Output file path (defaults to timestamped file in data/exports/)

    Returns:
        Path to exported file
    """
    database_path = database_path or config.database_path

    # Generate output path if not provided
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"candidate_summary_{timestamp}.md"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load candidates
    candidates = _load_candidates_with_metrics(database_path)

    # Generate markdown
    _write_markdown_summary(candidates, output_path)

    return str(output_path)


def _write_markdown_summary(candidates: List[dict], output_path: Path):
    """
    Write Markdown summary report.

    Args:
        candidates: List of candidate dictionaries
        output_path: Output file path
    """
    lines = []

    # Title
    lines.append("# Market Sentry Candidate Analysis Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Summary statistics
    total = len(candidates)
    strong_review = sum(1 for c in candidates if c["review_recommendation"] == "strong_review")
    review = sum(1 for c in candidates if c["review_recommendation"] == "review")
    maybe_review = sum(1 for c in candidates if c["review_recommendation"] == "maybe_review")
    reject_noise = sum(1 for c in candidates if c["review_recommendation"] == "reject_location_noise")
    needs_data = sum(1 for c in candidates if c["review_recommendation"] == "needs_more_data")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Candidates**: {total}")
    lines.append(f"- **Strong Review**: {strong_review}")
    lines.append(f"- **Review**: {review}")
    lines.append(f"- **Maybe Review**: {maybe_review}")
    lines.append(f"- **Reject (Location Noise)**: {reject_noise}")
    lines.append(f"- **Needs More Data**: {needs_data}")
    lines.append("")

    # Top candidates
    top_candidates = sorted(
        [c for c in candidates if c["overall_review_score"]],
        key=lambda x: float(x["overall_review_score"]),
        reverse=True
    )[:10]

    if top_candidates:
        lines.append("## Top 10 Candidates")
        lines.append("")
        lines.append("| Rank | Address | Score | Location | DOM Delta | Flags |")
        lines.append("|------|---------|-------|----------|-----------|-------|")

        for i, c in enumerate(top_candidates, 1):
            address = c["address"][:30] if len(c["address"]) > 30 else c["address"]
            score = c["overall_review_score"]
            location = c["location_fit_label"].replace("_", " ")[:20] if c["location_fit_label"] else "N/A"
            dom_delta = c["effective_dom_delta"] or "N/A"
            positive_flags = c["positive_flags"][:30] if c["positive_flags"] else "None"

            lines.append(f"| {i} | {address} | {score} | {location} | {dom_delta} | {positive_flags} |")

        lines.append("")

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
