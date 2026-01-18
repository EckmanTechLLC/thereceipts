"""
Response Formatter for conversational chat responses.

Converts claim cards into conversational response format while
maintaining claim card structure.
"""

from typing import Dict, Any
from database.models import ClaimCard


def format_claim_card_for_chat(
    claim_card: ClaimCard,
    contextualized_question: str
) -> Dict[str, Any]:
    """
    Format claim card as conversational chat response.

    Converts claim card to JSON format suitable for chat UI
    while maintaining all claim card data and structure.

    Args:
        claim_card: ClaimCard model instance with all relationships loaded
        contextualized_question: The contextualized question used for retrieval

    Returns:
        Dict containing:
            - type: 'existing' or 'generated'
            - contextualized_question: The reformulated question
            - claim_card: Full claim card object with all relationships
    """
    return {
        "type": "existing",
        "contextualized_question": contextualized_question,
        "claim_card": {
            "id": str(claim_card.id),
            "claim_text": claim_card.claim_text,
            "claimant": claim_card.claimant,
            "claim_type": claim_card.claim_type,
            "verdict": claim_card.verdict.value,
            "short_answer": claim_card.short_answer,
            "deep_answer": claim_card.deep_answer,
            "why_persists": claim_card.why_persists,
            "confidence_level": claim_card.confidence_level.value,
            "confidence_explanation": claim_card.confidence_explanation,
            "agent_audit": claim_card.agent_audit,
            "created_at": claim_card.created_at.isoformat(),
            "updated_at": claim_card.updated_at.isoformat(),
            "sources": [
                {
                    "id": str(s.id),
                    "source_type": s.source_type.value,
                    "citation": s.citation,
                    "url": s.url,
                    "quote_text": s.quote_text,
                    "usage_context": s.usage_context,
                    # Phase 4.1: Verification metadata
                    "verification_method": s.verification_method,
                    "verification_status": s.verification_status,
                    "content_type": s.content_type,
                    "url_verified": s.url_verified,
                }
                for s in claim_card.sources
            ],
            "apologetics_tags": [
                {
                    "id": str(at.id),
                    "technique_name": at.technique_name,
                    "description": at.description,
                }
                for at in claim_card.apologetics_tags
            ],
            "category_tags": [
                {
                    "id": str(ct.id),
                    "category_name": ct.category_name,
                    "description": ct.description,
                }
                for ct in claim_card.category_tags
            ],
        }
    }


def format_generating_response(
    pipeline_id: str,
    websocket_session_id: str,
    contextualized_question: str
) -> Dict[str, Any]:
    """
    Format response for pipeline generation in progress.

    Args:
        pipeline_id: Unique ID for this pipeline run
        websocket_session_id: WebSocket session ID for progress updates
        contextualized_question: The reformulated question

    Returns:
        Dict containing:
            - type: 'generating'
            - pipeline_id: UUID for this pipeline run
            - websocket_session_id: Session ID for WebSocket connection
            - contextualized_question: The reformulated question
            - message: Status message for user
    """
    return {
        "type": "generating",
        "pipeline_id": pipeline_id,
        "websocket_session_id": websocket_session_id,
        "contextualized_question": contextualized_question,
        "message": "Generating claim card through 5-agent pipeline. Connect to WebSocket for progress updates."
    }
