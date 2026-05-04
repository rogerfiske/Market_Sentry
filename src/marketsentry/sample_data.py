"""Sample/seed data generation for testing the review workflow."""

from datetime import date
from typing import List

from marketsentry.database import insert_candidates
from marketsentry.gas_detection import detect_gas_service
from marketsentry.logging_config import logger
from marketsentry.models import CandidateProperty
from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper


def create_sample_candidates() -> List[CandidateProperty]:
    """
    Create sample candidate properties for testing.

    Returns:
        List of sample candidate properties
    """
    candidates = []

    # Sample 1: Strong Quiet/Vibrancy match with gas service
    gas_evidence_1 = "Gas fireplace, gas range in kitchen, gas dryer hookup"
    has_gas_1, evidence_1 = detect_gas_service(gas_evidence_1)
    gatekeeper_1, _ = apply_quiet_gatekeeper(9.2, 1.8)

    candidate_1 = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house,min-price=550k,max-price=990k,min-beds=2,min-baths=2,min-parking=2,pool-type=no-private",
        redfin_url="https://www.redfin.com/CA/Temecula/12345-Sample-St-92592/home/123456789",
        address="12345 Sample St",
        city="Temecula",
        zip="92592",
        price=725000.0,
        beds=3,
        baths=2.5,
        sqft=2100,
        lot_size=0.25,
        displayed_dom=45,
        quiet_score=9.2,
        vibrancy_score=1.8,
        quiet_gatekeeper_result=gatekeeper_1,
        garage_spaces=2,
        gas_service=has_gas_1,
        gas_evidence=evidence_1,
        effective_dom_estimate=120,
        listing_churn_count=3,
        dom_reset_count=2,
        sale_rent_alternation_count=0,
        review_status="pending",
    )
    candidates.append(candidate_1)

    # Sample 2: Low Quiet score (fails gatekeeper) - even though Vibrancy is low
    gatekeeper_2, _ = apply_quiet_gatekeeper(5.5, 2.0)

    candidate_2 = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="https://www.redfin.com/city/12866/CA/Murrieta/filter/property-type=house,min-price=550k,max-price=990k,min-beds=2,min-baths=2,min-parking=2,pool-type=no-private",
        redfin_url="https://www.redfin.com/CA/Murrieta/67890-Busy-Ave-92563/home/987654321",
        address="67890 Busy Ave",
        city="Murrieta",
        zip="92563",
        price=650000.0,
        beds=3,
        baths=2.0,
        sqft=1850,
        lot_size=0.18,
        displayed_dom=30,
        quiet_score=5.5,  # Below minimum threshold
        vibrancy_score=2.0,  # Low, but doesn't matter due to quiet score
        quiet_gatekeeper_result=gatekeeper_2,
        garage_spaces=2,
        gas_service=False,
        gas_evidence=None,
        effective_dom_estimate=35,
        listing_churn_count=1,
        dom_reset_count=0,
        sale_rent_alternation_count=0,
        review_status="pending",
    )
    candidates.append(candidate_2)

    # Sample 3: Missing Quiet/Vibrancy data - needs more review
    candidate_3 = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house,min-price=550k,max-price=990k,min-beds=2,min-baths=2,min-parking=2,pool-type=no-private",
        redfin_url="https://www.redfin.com/CA/Temecula/11111-Unknown-Rd-92591/home/111222333",
        address="11111 Unknown Rd",
        city="Temecula",
        zip="92591",
        price=799000.0,
        beds=4,
        baths=3.0,
        sqft=2450,
        lot_size=0.32,
        displayed_dom=15,
        quiet_score=None,  # Missing
        vibrancy_score=None,  # Missing
        quiet_gatekeeper_result="fail_no_data",
        garage_spaces=3,
        gas_service=True,
        gas_evidence="Gas heating, gas water heater",
        effective_dom_estimate=None,
        listing_churn_count=None,
        dom_reset_count=None,
        sale_rent_alternation_count=None,
        review_status="pending",
    )
    candidates.append(candidate_3)

    return candidates


def seed_sample_candidates(database_path: str = None) -> int:
    """
    Seed the database with sample candidates for testing.

    Args:
        database_path: Path to database file

    Returns:
        Number of candidates inserted
    """
    candidates = create_sample_candidates()

    # Insert candidates (skip if exists)
    ids = insert_candidates(candidates, skip_if_exists=True, database_path=database_path)

    logger.info(f"Seeded {len(ids)} sample candidates into database")

    return len(ids)
