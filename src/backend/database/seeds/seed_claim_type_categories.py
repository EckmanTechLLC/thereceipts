"""
Seed script to populate claim_type_category for existing claim cards.

Analyzes existing claim cards and assigns appropriate claim type categories:
- historical: Claims about historical events (flood, exodus, resurrection)
- epistemology: Claims about knowledge/evidence (unfalsifiability, faith vs reason)
- interpretation: Claims about biblical interpretation (symbolism, prophecy)
- theological: Claims about God's nature/attributes (omnipotence, morality)
- textual: Claims about biblical texts (contradictions, authorship, translation)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.session import AsyncSessionFactory
from database.repositories import ClaimCardRepository


# Mapping of keywords to claim type categories
CATEGORY_KEYWORDS = {
    "historical": [
        "flood", "noah", "exodus", "moses", "resurrection", "jesus", "tomb",
        "archaeological", "evidence", "happened", "historical", "event"
    ],
    "epistemology": [
        "faith", "reason", "evidence", "prove", "unfalsifiable", "science",
        "knowledge", "belief", "testable", "hide", "disappear", "could god"
    ],
    "interpretation": [
        "symbolic", "literal", "metaphor", "interpretation", "prophecy",
        "context", "meaning", "represent", "allegory"
    ],
    "theological": [
        "god's nature", "omnipotent", "omniscient", "moral", "evil",
        "free will", "divine", "attributes", "trinitarian"
    ],
    "textual": [
        "contradiction", "authorship", "translation", "manuscript",
        "gospel", "canon", "verse", "text", "biblical"
    ]
}


async def determine_category(claim_text: str, claim_type: str) -> str:
    """
    Determine claim type category based on claim text and type.

    Args:
        claim_text: The text of the claim
        claim_type: Existing claim_type field

    Returns:
        Claim type category string
    """
    claim_lower = claim_text.lower()

    # Count keyword matches for each category
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in claim_lower)
        scores[category] = score

    # Return category with highest score, default to interpretation
    if max(scores.values()) == 0:
        # No keywords matched, use claim_type as fallback
        if claim_type:
            if "history" in claim_type.lower():
                return "historical"
            elif "doctrine" in claim_type.lower():
                return "theological"
            elif "science" in claim_type.lower():
                return "epistemology"
        return "interpretation"

    return max(scores, key=scores.get)


async def seed_claim_type_categories():
    """Populate claim_type_category for all existing claim cards."""
    async with AsyncSessionFactory() as session:
        repo = ClaimCardRepository(session)

        # Get all claim cards
        all_claims = await repo.get_all()
        print(f"Found {len(all_claims)} claim cards to process")

        updated_count = 0
        for claim in all_claims:
            if not claim.claim_type_category:
                # Determine category
                category = await determine_category(claim.claim_text, claim.claim_type)

                # Update claim
                claim.claim_type_category = category
                session.add(claim)
                updated_count += 1

                print(f"  [{claim.id}] {claim.claim_text[:60]}... -> {category}")

        # Commit all updates
        await session.commit()
        print(f"\nUpdated {updated_count} claim cards with claim_type_category")


async def main():
    """Main execution."""
    print("=" * 80)
    print("Seeding claim_type_category for existing claim cards")
    print("=" * 80)

    try:
        await seed_claim_type_categories()
        print("\n✓ Seed completed successfully")
    except Exception as e:
        print(f"\n✗ Error during seed: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
