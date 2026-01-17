"""
Router Service for TheReceipts intelligent routing.

Provides tool implementation for Router Agent:
- search_existing_claims: Semantic search via pgvector
- get_claim_details: Fetch claim card by ID
- generate_new_claim: Trigger pipeline orchestrator

Also handles logging routing decisions to router_decisions table.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories import ClaimCardRepository
from services.embedding import EmbeddingService


class RouterService:
    """Service layer for Router Agent tool implementations."""

    def __init__(self, db_session: AsyncSession):
        """Initialize with database session."""
        self.db_session = db_session
        self.claim_repo = ClaimCardRepository(db_session)
        self.embedding_service = EmbeddingService()

    async def search_existing_claims(
        self,
        query: str,
        threshold: float = 0.92,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for existing claim cards using semantic similarity.

        Args:
            query: Search query (typically reformulated question)
            threshold: Minimum similarity score (0-1)
            limit: Maximum number of results

        Returns:
            List of dicts containing:
                - claim_id: UUID
                - claim_text: Text of the claim
                - short_answer: Brief answer
                - similarity: Cosine similarity score (0-1)
                - claim_type: Type of claim
        """
        # Generate embedding for query
        query_embedding = await self.embedding_service.generate_embedding(query)

        # Search via pgvector (returns list of tuples: (ClaimCard, similarity_score))
        results = await self.claim_repo.search_by_embedding(
            embedding=query_embedding,
            threshold=threshold,
            limit=limit
        )

        # Format results for Router Agent
        formatted_results = []
        for claim_card, similarity in results:
            formatted_results.append({
                "claim_id": str(claim_card.id),
                "claim_text": claim_card.claim_text,
                "short_answer": claim_card.short_answer,
                "similarity": similarity,
                "claim_type": claim_card.claim_type,
                "claim_type_category": claim_card.claim_type_category,
                "verdict": claim_card.verdict.value if claim_card.verdict else None
            })

        return formatted_results

    async def get_claim_details(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve full details of a specific claim card.

        Args:
            claim_id: UUID string of claim card

        Returns:
            Dict with full claim card data, or None if not found
        """
        try:
            claim_uuid = UUID(claim_id)
        except ValueError:
            return None

        claim = await self.claim_repo.get_by_id(claim_uuid)
        if not claim:
            return None

        # Return comprehensive claim data
        return {
            "claim_id": str(claim.id),
            "claim_text": claim.claim_text,
            "claimant": claim.claimant,
            "claim_type": claim.claim_type,
            "claim_type_category": claim.claim_type_category,
            "verdict": claim.verdict.value if claim.verdict else None,
            "short_answer": claim.short_answer,
            "deep_answer": claim.deep_answer,
            "confidence_level": claim.confidence_level.value if claim.confidence_level else None,
            "confidence_explanation": claim.confidence_explanation,
            "why_persists": claim.why_persists,
            "created_at": claim.created_at.isoformat() if claim.created_at else None
        }

    async def generate_new_claim(
        self,
        question: str,
        reasoning: str
    ) -> Dict[str, Any]:
        """
        Trigger pipeline to generate new claim card.

        Args:
            question: User question requiring new claim
            reasoning: LLM's explanation for why this is novel

        Returns:
            Dict with pipeline trigger info:
                - status: "triggered"
                - question: Original question
                - reasoning: LLM reasoning
                - message: Info for user

        NOTE: This is Phase 3.1 foundation - actual pipeline integration
        happens in later phases. For now, just return trigger confirmation.
        """
        return {
            "status": "triggered",
            "question": question,
            "reasoning": reasoning,
            "message": (
                "Pipeline trigger confirmed. Full pipeline integration "
                "will be implemented in Phase 3.3."
            )
        }

    async def log_routing_decision(
        self,
        question_text: str,
        reformulated_question: str,
        conversation_context: List[Dict[str, str]],
        mode_selected: str,
        claim_cards_referenced: List[str],
        search_candidates: List[Dict[str, Any]],
        reasoning: str,
        response_time_ms: int
    ) -> UUID:
        """
        Log routing decision to router_decisions table for analysis.

        Args:
            question_text: Original user question
            reformulated_question: Context analyzer output
            conversation_context: Recent conversation history
            mode_selected: "EXACT_MATCH" | "CONTEXTUAL" | "NOVEL_CLAIM"
            claim_cards_referenced: List of claim UUIDs used in response
            search_candidates: Results from search_existing_claims
            reasoning: LLM's routing reasoning
            response_time_ms: Total routing time in milliseconds

        Returns:
            UUID of created router_decisions record
        """
        from database.models import RouterDecision, RoutingModeEnum
        from uuid import uuid4

        # Convert string UUIDs to UUID objects
        claim_uuids = [UUID(cid) for cid in claim_cards_referenced] if claim_cards_referenced else []

        # Map string mode to enum
        mode_enum = RoutingModeEnum(mode_selected)

        # Create decision record
        decision = RouterDecision(
            id=uuid4(),
            question_text=question_text,
            reformulated_question=reformulated_question,
            conversation_context=conversation_context,
            mode_selected=mode_enum,
            claim_cards_referenced=claim_uuids,
            search_candidates=search_candidates,
            reasoning=reasoning,
            response_time_ms=response_time_ms
        )

        self.db_session.add(decision)
        await self.db_session.commit()
        await self.db_session.refresh(decision)

        return decision.id
