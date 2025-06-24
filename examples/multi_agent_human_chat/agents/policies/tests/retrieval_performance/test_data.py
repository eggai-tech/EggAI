"""Test data for retrieval performance evaluation."""

from typing import List

from .models import RetrievalTestCase


def get_retrieval_test_cases() -> List[RetrievalTestCase]:
    """Get test dataset based on actual document content."""
    return [
        RetrievalTestCase(
            id="auto_policy_transferable",
            question="is this policy transferable?",
            expected_answer="No, this policy is non-transferable and applies exclusively to the vehicle(s) and authorized drivers listed in the policy schedule.",
            expected_chunk_ids=["auto_chunk_4"],
            category="auto",
            description="Test retrieval for policy transferability question in auto insurance",
        ),
        RetrievalTestCase(
            id="home_policy_transferable",
            question="can I transfer my home insurance policy?",
            expected_answer="No, the coverage is non-transferable except as may be expressly endorsed by the Insurer.",
            expected_chunk_ids=["home_chunk_3"],
            category="home",
            description="Test retrieval for home policy transferability",
        ),
        RetrievalTestCase(
            id="health_policy_transferable",
            question="is health insurance policy transferable?",
            expected_answer="No, this policy is non-transferable and applicable solely to the individual(s) named in the policy schedule.",
            expected_chunk_ids=["health_chunk_2"],
            category="health",
            description="Test retrieval for health policy transferability",
        ),
        RetrievalTestCase(
            id="home_water_damage_coverage",
            question="what is covered for water damage in home insurance?",
            expected_answer="Water damage from floods, heavy rainfall, dam breaches, and overflow from water bodies is covered under natural calamities.",
            expected_chunk_ids=["home_chunk_7", "home_chunk_8"],
            category="home",
            description="Test retrieval for water damage coverage in home insurance",
        ),
        RetrievalTestCase(
            id="life_death_benefit_amount",
            question="how much is the death benefit?",
            expected_answer="The Insurer shall pay a fixed lump-sum death benefit of [Fixed Coverage Amount] to the nominated beneficiaries.",
            expected_chunk_ids=["life_chunk_3"],
            category="life",
            description="Test retrieval for death benefit amount in life insurance",
        ),
        RetrievalTestCase(
            id="health_room_rent_limits",
            question="what are the room rent limits per day?",
            expected_answer="Room rent is capped at $200/day for standard rooms and $400/day for ICU.",
            expected_chunk_ids=["health_chunk_5"],
            category="health",
            description="Test retrieval for room rent limits in health insurance",
        ),
        RetrievalTestCase(
            id="health_copay_seniors",
            question="what is the copay for seniors?",
            expected_answer="Policyholders aged 60 years and above shall be required to bear 10% of all admissible claim amounts.",
            expected_chunk_ids=["health_chunk_15"],
            category="health",
            description="Test retrieval for senior citizen copay requirements",
        ),
        RetrievalTestCase(
            id="auto_collision_coverage_details",
            question="what does collision coverage include?",
            expected_answer="Collision coverage provides reimbursement for repair or replacement costs due to collision with another vehicle, stationary object, or any external impact, regardless of fault, subject to applicable deductibles.",
            expected_chunk_ids=["auto_chunk_6"],
            category="auto",
            description="Test retrieval for collision coverage details",
        ),
        RetrievalTestCase(
            id="life_terminal_illness_benefit",
            question="can I get money if I have terminal illness?",
            expected_answer="Yes, you may receive a portion of the death benefit as an advance if diagnosed with a terminal condition by a qualified medical practitioner.",
            expected_chunk_ids=["life_chunk_5"],
            category="life",
            description="Test retrieval for terminal illness benefit in life insurance",
        ),
        RetrievalTestCase(
            id="auto_claims_reporting_time",
            question="how long do I have to report an auto claim?",
            expected_answer="The Insured must notify the Insurer of any incident, accident, or loss within twenty-four (24) hours of occurrence.",
            expected_chunk_ids=["auto_chunk_22"],
            category="auto",
            description="Test retrieval for auto insurance claim reporting timeframe",
        ),
    ]