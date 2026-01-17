"""
Chat Pipeline Integration.

Handles pipeline execution for novel chat questions and persistence
of generated claim cards with embeddings.
"""

from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from services.pipeline import PipelineOrchestrator, PipelineError
from services.embedding import EmbeddingService, EmbeddingServiceError
from database.repositories import ClaimCardRepository


class ChatPipelineError(Exception):
    """Raised when chat pipeline execution fails."""
    pass


async def run_chat_pipeline(
    question: str,
    contextualized_question: str,
    websocket_session_id: str,
    db_session: AsyncSession,
    connection_manager: Any
) -> Dict[str, Any]:
    """
    Run pipeline for chat question and save result to database.

    Flow:
    1. Execute 5-agent pipeline via PipelineOrchestrator
    2. On success:
       - Save claim card to database
       - Generate and save embedding
       - Send 'claim_card_ready' event via WebSocket
    3. On failure:
       - Send 'pipeline_failed' event via WebSocket
       - Log error details

    Args:
        question: Original user question
        contextualized_question: Reformulated question with conversation context
        websocket_session_id: WebSocket session ID for progress updates
        db_session: Database session
        connection_manager: WebSocket connection manager

    Returns:
        Dict containing:
            - success: True if pipeline completed and claim card saved
            - claim_card_id: UUID of saved claim card (if success=True)
            - claim_card: Full claim card object (if success=True)
            - error: Error message (if success=False)

    Raises:
        ChatPipelineError: If pipeline or persistence fails
    """
    try:
        # Step 1: Run pipeline
        orchestrator = PipelineOrchestrator(db_session)
        pipeline_result = await orchestrator.run_pipeline(
            question=question,
            websocket_session_id=websocket_session_id,
            connection_manager=connection_manager
        )

        # Check if pipeline succeeded
        if not pipeline_result["success"]:
            # Pipeline failed - error already sent via WebSocket by orchestrator
            return {
                "success": False,
                "error": pipeline_result.get("error", "Pipeline failed"),
                "claim_card_id": None,
                "claim_card": None,
            }

        # Step 2: Save claim card to database
        claim_repo = ClaimCardRepository(db_session)
        claim_card = await claim_repo.create_from_pipeline_output(
            pipeline_data=pipeline_result["claim_card_data"],
            question=question
        )

        # Step 3: Generate and save embedding
        embedding_service = EmbeddingService()
        try:
            embedding = await embedding_service.generate_embedding(claim_card.claim_text)
            await claim_repo.upsert_embedding(claim_card.id, embedding)
            await db_session.commit()
        except EmbeddingServiceError as e:
            # Log error but don't fail - claim card is still usable
            print(f"Warning: Failed to generate embedding for claim card {claim_card.id}: {e}")
            await db_session.commit()

        # Step 4: Refresh to get all relationships
        await db_session.refresh(claim_card)
        claim_card_full = await claim_repo.get_by_id(claim_card.id)

        # Step 5: Send 'claim_card_ready' event via WebSocket
        if claim_card_full:
            await connection_manager.send_message(
                websocket_session_id,
                {
                    "type": "claim_card_ready",
                    "claim_card": {
                        "id": str(claim_card_full.id),
                        "claim_text": claim_card_full.claim_text,
                        "claimant": claim_card_full.claimant,
                        "claim_type": claim_card_full.claim_type,
                        "verdict": claim_card_full.verdict.value,
                        "short_answer": claim_card_full.short_answer,
                        "deep_answer": claim_card_full.deep_answer,
                        "why_persists": claim_card_full.why_persists,
                        "confidence_level": claim_card_full.confidence_level.value,
                        "confidence_explanation": claim_card_full.confidence_explanation,
                        "agent_audit": claim_card_full.agent_audit,
                        "created_at": claim_card_full.created_at.isoformat(),
                        "updated_at": claim_card_full.updated_at.isoformat(),
                        "sources": [
                            {
                                "id": str(s.id),
                                "source_type": s.source_type.value,
                                "citation": s.citation,
                                "url": s.url,
                                "quote_text": s.quote_text,
                                "usage_context": s.usage_context,
                            }
                            for s in claim_card_full.sources
                        ],
                        "apologetics_tags": [
                            {
                                "id": str(at.id),
                                "technique_name": at.technique_name,
                                "description": at.description,
                            }
                            for at in claim_card_full.apologetics_tags
                        ],
                        "category_tags": [
                            {
                                "id": str(ct.id),
                                "category_name": ct.category_name,
                                "description": ct.description,
                            }
                            for ct in claim_card_full.category_tags
                        ],
                    }
                }
            )

        return {
            "success": True,
            "claim_card_id": str(claim_card.id),
            "claim_card": claim_card_full,
            "error": None,
        }

    except PipelineError as e:
        raise ChatPipelineError(f"Pipeline execution failed: {str(e)}")
    except Exception as e:
        raise ChatPipelineError(f"Unexpected error in chat pipeline: {str(e)}")
