"""
Standard category names for TheReceipts claim cards.

These categories provide broad UI navigation per ADR 001.
Category tags are assigned when claim cards are created.
"""

# Standard categories for UI navigation (from NOTES.md)
STANDARD_CATEGORIES = [
    {
        "name": "Genesis",
        "description": "Claims about origins, creation, cosmology, and early biblical narratives"
    },
    {
        "name": "Canon",
        "description": "Claims about biblical text formation, manuscript reliability, and canonization"
    },
    {
        "name": "Doctrine",
        "description": "Claims about core theological beliefs, interpretations, and dogma"
    },
    {
        "name": "Ethics",
        "description": "Claims about moral teachings, commandments, and biblical ethics"
    },
    {
        "name": "Institutions",
        "description": "Claims about church history, religious organizations, and institutional practices"
    },
]

"""
Usage Note:
-----------
Category tags are assigned to claim cards when they are created by the agent pipeline.
The Writing Agent or Publisher Agent determines which categories apply to each claim.

Multiple categories can be assigned to a single claim card.
Category names are flexible (not enum) to allow future expansion beyond these standard five.

Example:
    category_tag = CategoryTag(
        claim_card_id=claim_card.id,
        category_name="Genesis",
        description="This claim relates to creation narratives"
    )
"""
