"""
TheReceipts FastAPI application.

Main entry point for the backend API server.
"""

from typing import List, Optional, Dict
from fastapi import FastAPI, Depends, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import json
import uuid
from uuid import UUID
import asyncio
from datetime import datetime

from config import settings
from database.session import get_db, AsyncSessionFactory
from database.repositories import (
    ClaimCardRepository,
    AgentPromptRepository,
    TopicQueueRepository,
    CategoryTagRepository,
    BlogPostRepository,
)
from database.models import TopicStatusEnum, TopicQueue, ReviewStatusEnum
from services.pipeline import PipelineOrchestrator, PipelineError
from services.context_analyzer import ContextAnalyzer, ContextAnalyzerError
from services.embedding import EmbeddingService, EmbeddingServiceError
from services.llm_client import LLMClient
from services.chat_pipeline import run_chat_pipeline, ChatPipelineError
from services.response_formatter import format_claim_card_for_chat, format_generating_response
from services.router_service import RouterService
from services.scheduler import scheduler_service, SchedulerConfig, SchedulerServiceError
from services.autosuggest import autosuggest_service, AutoSuggestConfig, AutoSuggestServiceError
from services.review import ReviewService, ReviewServiceError
from agents.router_agent import RouterAgent, AgentError


# Create FastAPI application
app = FastAPI(
    title="TheReceipts API",
    description="Religion claim analysis platform - API for audited Christianity claims",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket connection manager
class ConnectionManager:
    """
    Manages active WebSocket connections for real-time pipeline updates.

    Tracks connections by session_id to allow targeted broadcasting.
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_message(self, session_id: str, message: dict):
        """
        Send a message to a specific session.

        Args:
            session_id: Session identifier
            message: Dictionary to send as JSON
        """
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
            except Exception:
                # Connection closed, remove it
                self.disconnect(session_id)


# Global connection manager instance
manager = ConnectionManager()


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    print("Starting scheduler service...")
    scheduler_service.start()
    print(f"Scheduler service started (enabled: {scheduler_service.config.enabled})")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up services on application shutdown."""
    print("Shutting down scheduler service...")
    scheduler_service.shutdown()
    print("Scheduler service stopped")


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns basic service status.
    """
    return {
        "status": "healthy",
        "service": "thereceipts-api",
        "version": "0.1.0"
    }


@app.get("/api/claim-cards")
async def list_claim_cards(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    category: Optional[str] = Query(None, description="Filter by category name"),
    db: AsyncSession = Depends(get_db)
):
    """
    List claim cards with pagination and optional category filter.

    Args:
        skip: Offset for pagination (default: 0)
        limit: Number of records to return (default: 20, max: 100)
        category: Optional category name to filter by
        db: Database session

    Returns:
        List of claim cards with all relationships loaded
    """
    repo = ClaimCardRepository(db)
    claim_cards = await repo.get_all(skip=skip, limit=limit, category=category)

    # Convert to dict for JSON response
    return {
        "claim_cards": [
            {
                "id": str(cc.id),
                "claim_text": cc.claim_text,
                "claimant": cc.claimant,
                "claim_type": cc.claim_type,
                "verdict": cc.verdict.value,
                "short_answer": cc.short_answer,
                "deep_answer": cc.deep_answer,
                "why_persists": cc.why_persists,
                "confidence_level": cc.confidence_level.value,
                "confidence_explanation": cc.confidence_explanation,
                "agent_audit": cc.agent_audit,
                "created_at": cc.created_at.isoformat(),
                "updated_at": cc.updated_at.isoformat(),
                "sources": [
                    {
                        "id": str(s.id),
                        "source_type": s.source_type.value,
                        "citation": s.citation,
                        "url": s.url,
                        "quote_text": s.quote_text,
                        "usage_context": s.usage_context,
                    }
                    for s in cc.sources
                ],
                "apologetics_tags": [
                    {
                        "id": str(at.id),
                        "technique_name": at.technique_name,
                        "description": at.description,
                    }
                    for at in cc.apologetics_tags
                ],
                "category_tags": [
                    {
                        "id": str(ct.id),
                        "category_name": ct.category_name,
                        "description": ct.description,
                    }
                    for ct in cc.category_tags
                ],
            }
            for cc in claim_cards
        ],
        "pagination": {
            "skip": skip,
            "limit": limit,
            "count": len(claim_cards),
        }
    }


@app.get("/api/agent-prompts")
async def list_agent_prompts(db: AsyncSession = Depends(get_db)):
    """
    List all agent prompts.

    Returns:
        List of agent prompt configurations
    """
    repo = AgentPromptRepository(db)
    prompts = await repo.get_all()

    return {
        "agent_prompts": [
            {
                "id": str(ap.id),
                "agent_name": ap.agent_name,
                "llm_provider": ap.llm_provider,
                "model_name": ap.model_name,
                "system_prompt": ap.system_prompt,
                "temperature": ap.temperature,
                "max_tokens": ap.max_tokens,
                "created_at": ap.created_at.isoformat(),
                "updated_at": ap.updated_at.isoformat(),
            }
            for ap in prompts
        ]
    }


@app.get("/api/topic-queue")
async def list_topic_queue(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    status: Optional[TopicStatusEnum] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db)
):
    """
    List topics in the queue with optional status filter.

    Args:
        skip: Offset for pagination (default: 0)
        limit: Number of records to return (default: 20, max: 100)
        status: Optional status to filter by (queued, processing, completed, failed)
        db: Database session

    Returns:
        List of topics ordered by priority (descending)
    """
    repo = TopicQueueRepository(db)
    topics = await repo.get_all(skip=skip, limit=limit, status=status)

    return {
        "topics": [
            {
                "id": str(t.id),
                "topic_text": t.topic_text,
                "priority": t.priority,
                "status": t.status.value,
                "source": t.source,
                "claim_card_ids": t.claim_card_ids,
                "scheduled_for": t.scheduled_for.isoformat() if t.scheduled_for else None,
                "error_message": t.error_message,
                "retry_count": t.retry_count,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in topics
        ],
        "pagination": {
            "skip": skip,
            "limit": limit,
            "count": len(topics),
        }
    }


@app.get("/api/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """
    List unique category names across all claim cards.

    Returns:
        List of category names (sorted alphabetically)
    """
    repo = CategoryTagRepository(db)
    categories = await repo.get_unique_categories()

    return {
        "categories": categories,
        "count": len(categories),
    }


# Pydantic models for chat and pipeline endpoints
class ChatMessage(BaseModel):
    """Chat message structure."""
    role: str  # 'user' or 'assistant'
    content: str


class ChatMessageRequest(BaseModel):
    """Request model for chat message endpoint."""
    message: str
    conversation_history: Optional[List[ChatMessage]] = None


class PipelineTestRequest(BaseModel):
    """Request model for pipeline test endpoint."""
    question: str
    websocket_session_id: Optional[str] = None


class ChatAskRequest(BaseModel):
    """Request model for intelligent routing chat endpoint."""
    question: str
    conversation_history: Optional[List[ChatMessage]] = None


# Pydantic models for admin endpoints (Phase 3.1)
class AdminTopicCreateRequest(BaseModel):
    """Request model for creating a topic in the queue."""
    topic_text: str
    priority: int = 0
    source: Optional[str] = "manual"


class AdminTopicUpdateRequest(BaseModel):
    """Request model for updating a topic in the queue."""
    topic_text: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    source: Optional[str] = None


class SchedulerSettingsRequest(BaseModel):
    """Request model for scheduler configuration."""
    enabled: bool
    posts_per_day: int = 1
    cron_hour: int = 2
    cron_minute: int = 0


class AutoSuggestSettingsRequest(BaseModel):
    """Request model for auto-suggest configuration."""
    enabled: bool
    max_topics_per_run: int = 10
    similarity_threshold: float = 0.85


class AutoSuggestExtractRequest(BaseModel):
    """Request model for extracting topics from text."""
    source_text: str
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    skip_deduplication: bool = False


class ReviewApproveRequest(BaseModel):
    """Request model for approving a blog post."""
    reviewed_by: str
    review_notes: Optional[str] = None


class ReviewRejectRequest(BaseModel):
    """Request model for rejecting a blog post."""
    reviewed_by: str
    admin_feedback: str


class ReviewRevisionRequest(BaseModel):
    """Request model for requesting revision of a blog post."""
    reviewed_by: str
    admin_feedback: str
    revision_scope: str  # "decomposer", "claim_pipeline", "composer"
    revision_details: Optional[Dict] = None  # e.g., {"claim_card_ids": ["uuid1", "uuid2"]}


class DatabaseResetRequest(BaseModel):
    """Request model for database reset confirmation."""
    confirm: bool


async def run_pipeline_background_task(
    question: str,
    contextualized_question: str,
    websocket_session_id: str,
    connection_manager: ConnectionManager
):
    """
    Background task wrapper for pipeline execution with its own database session.

    Creates a new database session to avoid using the closed request session.
    Catches and logs all exceptions to prevent silent failures.
    """
    async with AsyncSessionFactory() as db_session:
        try:
            await run_chat_pipeline(
                question=question,
                contextualized_question=contextualized_question,
                websocket_session_id=websocket_session_id,
                db_session=db_session,
                connection_manager=connection_manager
            )
        except Exception as e:
            print(f"[Background Task] Pipeline failed: {str(e)}")
            import traceback
            traceback.print_exc()
            # Send failure event via WebSocket
            await connection_manager.send_message(
                websocket_session_id,
                {
                    "type": "pipeline_failed",
                    "error": str(e),
                    "timestamp": None,
                    "duration": 0
                }
            )


@app.post("/api/chat/message")
async def chat_message(
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Conversational chat endpoint with context analysis and semantic search.

    Flow:
    1. Context Analyzer reformulates question with conversation history
    2. Generate embedding for contextualized question
    3. Semantic search existing claim cards
    4. If match >0.85: Return existing card
    5. If no match: Return status='generating' (pipeline would run via WebSocket)

    Args:
        request: JSON body containing:
            - message: User's new message
            - conversation_history: Optional list of previous messages

        db: Database session

    Returns:
        JSON response containing:
        - type: 'existing' or 'generating'
        - claim_card: Full claim card object (if type='existing')
        - pipeline_status: 'queued' (if type='generating')
        - contextualized_question: The reformulated question used for search

    Raises:
        HTTPException: If request is invalid or services fail
    """
    # Validate message
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if len(request.message) > settings.MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Message too long. Maximum {settings.MAX_MESSAGE_LENGTH} characters allowed."
        )

    # Validate conversation history length
    if request.conversation_history and len(request.conversation_history) > settings.MAX_CONVERSATION_HISTORY:
        raise HTTPException(
            status_code=400,
            detail=f"Conversation history too long. Maximum {settings.MAX_CONVERSATION_HISTORY} messages allowed."
        )

    try:
        # Initialize services
        llm_client = LLMClient()
        context_analyzer = ContextAnalyzer(llm_client)
        embedding_service = EmbeddingService()
        claim_repo = ClaimCardRepository(db)

        # Step 1: Reformulate question with conversation context
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in (request.conversation_history or [])
        ]

        contextualized_question = await context_analyzer.analyze_context(
            conversation_history=conversation_history,
            new_message=request.message
        )

        # Step 2: Generate embedding for contextualized question
        query_embedding = await embedding_service.generate_embedding(
            contextualized_question
        )

        # Step 3: Semantic search existing claim cards
        search_results = await claim_repo.search_by_embedding(
            embedding=query_embedding,
            threshold=settings.SEMANTIC_SEARCH_THRESHOLD,
            limit=5
        )

        # Step 4: Check if we have a match
        if search_results:
            # Found a matching claim card - return it
            best_match, similarity = search_results[0]
            return format_claim_card_for_chat(best_match, contextualized_question)
        else:
            # No match found - trigger pipeline generation
            pipeline_id = str(uuid.uuid4())
            websocket_session_id = str(uuid.uuid4())

            # Start pipeline in background (non-blocking)
            asyncio.create_task(
                run_pipeline_background_task(
                    question=request.message,
                    contextualized_question=contextualized_question,
                    websocket_session_id=websocket_session_id,
                    connection_manager=manager
                )
            )

            # Return immediately with pipeline info
            return format_generating_response(
                pipeline_id=pipeline_id,
                websocket_session_id=websocket_session_id,
                contextualized_question=contextualized_question
            )

    except ContextAnalyzerError as e:
        raise HTTPException(
            status_code=500,
            detail="Unable to process your question with conversation context. Please try rephrasing or starting a new conversation."
        )
    except EmbeddingServiceError as e:
        raise HTTPException(
            status_code=500,
            detail="Unable to search existing claim cards. Please try again in a moment."
        )
    except Exception as e:
        # Log the actual error for debugging
        print(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again."
        )


@app.post("/api/chat/ask")
async def chat_ask(
    request: ChatAskRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Intelligent routing chat endpoint using Context Analyzer + Router Agent.

    Flow:
    1. Context Analyzer reformulates question with conversation history
    2. Router Agent decides routing mode (exact_match, contextual, or novel_claim)
    3. Based on mode:
       - Mode 1 (exact_match): Return existing claim card
       - Mode 2 (contextual): Return synthesized response from existing cards
       - Mode 3 (novel_claim): Trigger full 5-agent pipeline
    4. Log routing decision to router_decisions table

    Args:
        request: JSON body containing:
            - question: User's question
            - conversation_history: Optional list of previous messages

        db: Database session

    Returns:
        JSON response containing:
        - mode: "exact_match" | "contextual" | "novel_claim"
        - response: Mode-specific response data
        - websocket_session_id: For Mode 3 (pipeline progress tracking)
        - routing_decision_id: UUID of logged routing decision

    Raises:
        HTTPException: If request is invalid or processing fails
    """
    import time

    # Validate question
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if len(request.question) > settings.MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Question too long. Maximum {settings.MAX_MESSAGE_LENGTH} characters allowed."
        )

    # Validate conversation history length
    if request.conversation_history and len(request.conversation_history) > settings.MAX_CONVERSATION_HISTORY:
        raise HTTPException(
            status_code=400,
            detail=f"Conversation history too long. Maximum {settings.MAX_CONVERSATION_HISTORY} messages allowed."
        )

    start_time = time.time()

    try:
        # Initialize services
        llm_client = LLMClient()
        context_analyzer = ContextAnalyzer(llm_client)
        router_service = RouterService(db)
        claim_repo = ClaimCardRepository(db)

        # Step 1: Reformulate question with conversation context
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in (request.conversation_history or [])
        ]

        # Send WebSocket event: Context analysis started
        websocket_session_id = str(uuid.uuid4())
        await manager.send_message(
            websocket_session_id,
            {
                "type": "context_analysis_started",
                "timestamp": datetime.now().isoformat()
            }
        )

        contextualized_question = await context_analyzer.analyze_context(
            conversation_history=conversation_history,
            new_message=request.question
        )

        # Send WebSocket event: Routing started
        await manager.send_message(
            websocket_session_id,
            {
                "type": "routing_started",
                "contextualized_question": contextualized_question,
                "timestamp": datetime.now().isoformat()
            }
        )

        # Step 2: Call Router Agent
        try:
            router_agent = RouterAgent(db)
            router_result = await router_agent.execute({
                "reformulated_question": contextualized_question,
                "original_question": request.question,
                "conversation_history": conversation_history
            })

            mode = router_result["mode"]
            tool_results = router_result["tool_results"]
            final_answer = router_result.get("final_answer", "")

        except AgentError as e:
            # Router failed - fallback to Mode 3 (novel claim)
            print(f"Router Agent failed, falling back to Mode 3: {str(e)}")

            await manager.send_message(
                websocket_session_id,
                {
                    "type": "router_fallback",
                    "reason": "Router Agent failed, generating new claim",
                    "timestamp": datetime.now().isoformat()
                }
            )

            mode = "NOVEL_CLAIM"
            tool_results = []
            final_answer = ""

        # Step 3: Handle mode-specific responses
        response_data = None
        claim_cards_referenced = []
        search_candidates = []

        # Extract search_candidates from tool_results for logging (regardless of mode)
        for tool_result in tool_results:
            if tool_result["tool_name"] == "search_existing_claims":
                search_candidates = tool_result["tool_result"].get("results", [])
                break

        if mode == "EXACT_MATCH":
            # Mode 1: Return existing claim card
            # Extract claim_id from tool results
            claim_id = None
            for tool_result in tool_results:
                if tool_result["tool_name"] == "search_existing_claims":
                    results = tool_result["tool_result"].get("results", [])
                    if results:
                        claim_id = results[0]["claim_id"]
                        search_candidates = results
                        break

            if claim_id:
                claim = await claim_repo.get_by_id(UUID(claim_id))
                if claim:
                    claim_cards_referenced.append(claim_id)
                    response_data = {
                        "type": "exact_match",
                        "claim_card": format_claim_card_for_chat(claim, contextualized_question)["claim_card"]
                    }

            # Fallback if claim not found
            if not response_data:
                mode = "NOVEL_CLAIM"

        if mode == "CONTEXTUAL":
            # Mode 2: Return synthesized response with source cards
            # Extract referenced claim IDs from tool results
            for tool_result in tool_results:
                if tool_result["tool_name"] == "search_existing_claims":
                    search_candidates = tool_result["tool_result"].get("results", [])
                elif tool_result["tool_name"] == "get_claim_details":
                    claim_data = tool_result["tool_result"].get("claim")
                    if claim_data:
                        claim_cards_referenced.append(claim_data["claim_id"])

            # If no get_claim_details was called, use search candidates as source cards
            if not claim_cards_referenced and search_candidates:
                for candidate in search_candidates[:3]:  # Top 3 candidates
                    claim_cards_referenced.append(candidate["claim_id"])

            # Fetch full claim card objects for referenced cards
            source_cards = []
            for claim_id in claim_cards_referenced:
                claim = await claim_repo.get_by_id(UUID(claim_id))
                if claim:
                    source_cards.append({
                        "id": str(claim.id),
                        "claim_text": claim.claim_text,
                        "claimant": claim.claimant,
                        "claim_type": claim.claim_type,
                        "verdict": claim.verdict.value,
                        "short_answer": claim.short_answer,
                        "deep_answer": claim.deep_answer,
                        "why_persists": claim.why_persists,
                        "confidence_level": claim.confidence_level.value if claim.confidence_level else "MEDIUM",
                        "confidence_explanation": claim.confidence_explanation,
                        "agent_audit": claim.agent_audit,
                        "created_at": claim.created_at.isoformat(),
                        "updated_at": claim.updated_at.isoformat(),
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
                            for s in claim.sources
                        ],
                        "apologetics_tags": [
                            {
                                "id": str(at.id),
                                "technique_name": at.technique_name,
                                "description": at.description,
                            }
                            for at in claim.apologetics_tags
                        ],
                        "category_tags": [
                            {
                                "id": str(ct.id),
                                "category_name": ct.category_name,
                                "description": ct.description,
                            }
                            for ct in claim.category_tags
                        ],
                    })

            response_data = {
                "type": "contextual",
                "synthesized_response": final_answer,
                "source_cards": source_cards
            }

        if mode == "NOVEL_CLAIM" or not response_data:
            # Mode 3: Trigger pipeline
            response_data = {
                "type": "generating",
                "pipeline_status": "queued",
                "websocket_session_id": websocket_session_id,
                "contextualized_question": contextualized_question
            }

            # Start pipeline in background
            asyncio.create_task(
                run_pipeline_background_task(
                    question=request.question,
                    contextualized_question=contextualized_question,
                    websocket_session_id=websocket_session_id,
                    connection_manager=manager
                )
            )

        # Step 4: Log routing decision
        response_time_ms = int((time.time() - start_time) * 1000)

        # Extract reasoning from tool results or final answer
        reasoning = final_answer[:500] if final_answer else "Router Agent routing decision"

        decision_id = await router_service.log_routing_decision(
            question_text=request.question,
            reformulated_question=contextualized_question,
            conversation_context=conversation_history,
            mode_selected=mode,
            claim_cards_referenced=claim_cards_referenced,
            search_candidates=search_candidates,
            reasoning=reasoning,
            response_time_ms=response_time_ms
        )

        # Send WebSocket event: Routing completed
        await manager.send_message(
            websocket_session_id,
            {
                "type": "routing_completed",
                "mode": mode,
                "response_time_ms": response_time_ms,
                "timestamp": datetime.now().isoformat()
            }
        )

        return {
            "mode": mode,
            "response": response_data,
            "routing_decision_id": str(decision_id),
            "websocket_session_id": websocket_session_id if mode == "NOVEL_CLAIM" else None
        }

    except ContextAnalyzerError as e:
        raise HTTPException(
            status_code=500,
            detail="Unable to process your question with conversation context. Please try rephrasing or starting a new conversation."
        )
    except Exception as e:
        # Log the actual error for debugging
        print(f"Unexpected error in chat/ask endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again."
        )


# Admin API endpoints (Phase 3.1: Topic Queue Management)
@app.post("/api/admin/topics")
async def admin_create_topic(
    request: AdminTopicCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new topic in the queue (admin only).

    Args:
        request: JSON body containing:
            - topic_text: Topic/claim to analyze
            - priority: Priority level (default: 0, higher = process sooner)
            - source: Where this topic came from (default: "manual")

        db: Database session

    Returns:
        Created topic with all fields

    Raises:
        HTTPException: If topic_text is empty or creation fails
    """
    if not request.topic_text or not request.topic_text.strip():
        raise HTTPException(status_code=400, detail="topic_text cannot be empty")

    try:
        repo = TopicQueueRepository(db)

        # Create new topic
        topic = TopicQueue(
            topic_text=request.topic_text.strip(),
            priority=request.priority,
            status=TopicStatusEnum.QUEUED,
            source=request.source or "manual"
        )

        created_topic = await repo.create(topic)
        await db.commit()

        return {
            "id": str(created_topic.id),
            "topic_text": created_topic.topic_text,
            "priority": created_topic.priority,
            "status": created_topic.status.value,
            "source": created_topic.source,
            "review_status": created_topic.review_status,
            "created_at": created_topic.created_at.isoformat(),
        }

    except Exception as e:
        await db.rollback()
        print(f"Error creating topic: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create topic")


@app.get("/api/admin/topics")
async def admin_list_topics(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all topics in the queue with filters (admin only).

    Args:
        skip: Offset for pagination (default: 0)
        limit: Number of records to return (default: 20, max: 100)
        status: Optional TopicStatusEnum filter (queued, processing, completed, failed)
        review_status: Optional ReviewStatusEnum filter (pending_review, approved, rejected, needs_revision)
        db: Database session

    Returns:
        List of topics ordered by priority (descending)
    """
    repo = TopicQueueRepository(db)

    # Convert status string to enum if provided
    status_enum = None
    if status:
        try:
            status_enum = TopicStatusEnum(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    topics = await repo.get_all(skip=skip, limit=limit, status=status_enum)

    # Apply review_status filter if provided (manual filter since repo doesn't support it yet)
    if review_status:
        topics = [t for t in topics if t.review_status == review_status]

    return {
        "topics": [
            {
                "id": str(t.id),
                "topic_text": t.topic_text,
                "priority": t.priority,
                "status": t.status.value,
                "source": t.source,
                "review_status": t.review_status,
                "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
                "admin_feedback": t.admin_feedback,
                "blog_post_id": str(t.blog_post_id) if t.blog_post_id else None,
                "claim_card_ids": t.claim_card_ids,
                "scheduled_for": t.scheduled_for.isoformat() if t.scheduled_for else None,
                "error_message": t.error_message,
                "retry_count": t.retry_count,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in topics
        ],
        "pagination": {
            "skip": skip,
            "limit": limit,
            "count": len(topics),
        }
    }


@app.put("/api/admin/topics/{topic_id}")
async def admin_update_topic(
    topic_id: UUID,
    request: AdminTopicUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a topic in the queue (admin only).

    Args:
        topic_id: UUID of the topic to update
        request: JSON body containing optional fields:
            - topic_text: Updated topic text
            - priority: Updated priority level
            - status: Updated status (queued, processing, completed, failed)
            - source: Updated source

        db: Database session

    Returns:
        Updated topic with all fields

    Raises:
        HTTPException: If topic not found or update fails
    """
    try:
        repo = TopicQueueRepository(db)
        topic = await repo.get_by_id(topic_id)

        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        # Update fields if provided
        if request.topic_text is not None:
            topic.topic_text = request.topic_text.strip()
        if request.priority is not None:
            topic.priority = request.priority
        if request.status is not None:
            try:
                topic.status = TopicStatusEnum(request.status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")
        if request.source is not None:
            topic.source = request.source

        updated_topic = await repo.update(topic)
        await db.commit()

        return {
            "id": str(updated_topic.id),
            "topic_text": updated_topic.topic_text,
            "priority": updated_topic.priority,
            "status": updated_topic.status.value,
            "source": updated_topic.source,
            "review_status": updated_topic.review_status,
            "reviewed_at": updated_topic.reviewed_at.isoformat() if updated_topic.reviewed_at else None,
            "admin_feedback": updated_topic.admin_feedback,
            "blog_post_id": str(updated_topic.blog_post_id) if updated_topic.blog_post_id else None,
            "created_at": updated_topic.created_at.isoformat(),
            "updated_at": updated_topic.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error updating topic: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update topic")


@app.delete("/api/admin/topics/{topic_id}")
async def admin_delete_topic(
    topic_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a topic from the queue (admin only).

    Args:
        topic_id: UUID of the topic to delete
        db: Database session

    Returns:
        Success confirmation message

    Raises:
        HTTPException: If topic not found or deletion fails
    """
    try:
        repo = TopicQueueRepository(db)
        deleted = await repo.delete(topic_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Topic not found")

        await db.commit()

        return {
            "success": True,
            "message": "Topic deleted successfully",
            "topic_id": str(topic_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error deleting topic: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete topic")


# Admin API endpoints (Phase 3.3: Scheduler & Auto-Suggest)
@app.get("/api/admin/scheduler/settings")
async def admin_get_scheduler_settings():
    """
    Get current scheduler configuration (admin only).

    Returns:
        Scheduler configuration:
            - enabled: Whether scheduler is enabled
            - posts_per_day: Number of blog posts to generate per day
            - cron_hour: Hour to run scheduler (0-23, UTC)
            - cron_minute: Minute to run scheduler (0-59)
            - max_concurrent: Max concurrent generations (currently fixed at 1)
    """
    config = scheduler_service.config
    return {
        "enabled": config.enabled,
        "posts_per_day": config.posts_per_day,
        "cron_hour": config.cron_hour,
        "cron_minute": config.cron_minute,
        "max_concurrent": config.max_concurrent,
    }


@app.put("/api/admin/scheduler/settings")
async def admin_update_scheduler_settings(request: SchedulerSettingsRequest):
    """
    Update scheduler configuration (admin only).

    Args:
        request: JSON body containing:
            - enabled: Whether to enable scheduler
            - posts_per_day: Number of blog posts to generate per day
            - cron_hour: Hour to run scheduler (0-23, UTC)
            - cron_minute: Minute to run scheduler (0-59)

    Returns:
        Updated scheduler configuration

    Raises:
        HTTPException: If configuration is invalid
    """
    try:
        # Validate configuration
        if request.posts_per_day < 1 or request.posts_per_day > 10:
            raise HTTPException(
                status_code=400,
                detail="posts_per_day must be between 1 and 10"
            )

        if request.cron_hour < 0 or request.cron_hour > 23:
            raise HTTPException(
                status_code=400,
                detail="cron_hour must be between 0 and 23"
            )

        if request.cron_minute < 0 or request.cron_minute > 59:
            raise HTTPException(
                status_code=400,
                detail="cron_minute must be between 0 and 59"
            )

        # Update configuration
        config = SchedulerConfig(
            enabled=request.enabled,
            posts_per_day=request.posts_per_day,
            cron_hour=request.cron_hour,
            cron_minute=request.cron_minute
        )
        scheduler_service.configure(config)

        return {
            "success": True,
            "message": "Scheduler settings updated",
            "settings": {
                "enabled": config.enabled,
                "posts_per_day": config.posts_per_day,
                "cron_hour": config.cron_hour,
                "cron_minute": config.cron_minute,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating scheduler settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update scheduler settings")


@app.post("/api/admin/scheduler/run-now")
async def admin_run_scheduler_now():
    """
    Manually trigger blog post generation (admin only).

    Generates a single blog post from the highest priority queued topic.

    Returns:
        Generation result with blog post ID and metadata

    Raises:
        HTTPException: If generation fails or no topics queued
    """
    try:
        result = await scheduler_service.generate_next_blog_post()

        if not result:
            raise HTTPException(
                status_code=404,
                detail="No queued topics available for generation"
            )

        return {
            "success": True,
            "message": "Blog post generated successfully",
            "result": result
        }

    except SchedulerServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"Error running scheduler: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to run scheduler")


@app.get("/api/admin/autosuggest/settings")
async def admin_get_autosuggest_settings():
    """
    Get current auto-suggest configuration (admin only).

    Returns:
        Auto-suggest configuration:
            - enabled: Whether auto-suggest is enabled
            - max_topics_per_run: Max topics to extract per run
            - similarity_threshold: Deduplication threshold (0.0-1.0)
    """
    config = autosuggest_service.config
    return {
        "enabled": config.enabled,
        "max_topics_per_run": config.max_topics_per_run,
        "similarity_threshold": config.similarity_threshold,
        "default_priority": config.default_priority,
    }


@app.put("/api/admin/autosuggest/settings")
async def admin_update_autosuggest_settings(request: AutoSuggestSettingsRequest):
    """
    Update auto-suggest configuration (admin only).

    Args:
        request: JSON body containing:
            - enabled: Whether to enable auto-suggest
            - max_topics_per_run: Max topics to extract per run
            - similarity_threshold: Deduplication threshold (0.0-1.0)

    Returns:
        Updated auto-suggest configuration

    Raises:
        HTTPException: If configuration is invalid
    """
    try:
        # Validate configuration
        if request.max_topics_per_run < 1 or request.max_topics_per_run > 50:
            raise HTTPException(
                status_code=400,
                detail="max_topics_per_run must be between 1 and 50"
            )

        if request.similarity_threshold < 0.0 or request.similarity_threshold > 1.0:
            raise HTTPException(
                status_code=400,
                detail="similarity_threshold must be between 0.0 and 1.0"
            )

        # Update configuration
        config = AutoSuggestConfig(
            enabled=request.enabled,
            max_topics_per_run=request.max_topics_per_run,
            similarity_threshold=request.similarity_threshold
        )
        autosuggest_service.configure(config)

        return {
            "success": True,
            "message": "Auto-suggest settings updated",
            "settings": {
                "enabled": config.enabled,
                "max_topics_per_run": config.max_topics_per_run,
                "similarity_threshold": config.similarity_threshold,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating auto-suggest settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update auto-suggest settings")


@app.post("/api/admin/autosuggest/trigger")
async def admin_trigger_autosuggest(request: Optional[AutoSuggestExtractRequest] = None):
    """
    Manually trigger topic extraction from source text (admin only).

    Extracts apologetics topics from provided text, deduplicates against
    existing claim cards, and adds novel topics to the generation queue.

    Args:
        request: JSON body containing:
            - source_text: Text content from apologetics source
            - source_url: Optional URL of source
            - source_name: Optional name of source
            - skip_deduplication: If True, skip semantic search deduplication

    Returns:
        Extraction summary:
            - extracted: Number of topics extracted from text
            - added: Number of topics added to queue
            - skipped_duplicates: Number skipped due to existing similar claims
            - failed: Number that failed to add

    Raises:
        HTTPException: If extraction fails
    """
    # Validate request body and source_text
    if not request or not request.source_text:
        raise HTTPException(
            status_code=400,
            detail="source_text is required. This endpoint extracts topics from provided text. Use the admin UI form to paste apologetics content for analysis."
        )

    try:
        # Extract topics from text
        topics = await autosuggest_service.extract_topics_from_text(
            source_text=request.source_text,
            source_url=request.source_url,
            source_name=request.source_name
        )

        # Add topics to queue
        result = await autosuggest_service.add_topics_to_queue(
            topics=topics,
            skip_deduplication=request.skip_deduplication
        )

        return {
            "success": True,
            "message": f"Extracted {len(topics)} topics, added {result['added']} to queue",
            "extracted": len(topics),
            "added": result["added"],
            "skipped_duplicates": result["skipped_duplicates"],
            "failed": result["failed"],
        }

    except AutoSuggestServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"Error running auto-suggest: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to run auto-suggest")


@app.post("/api/admin/autosuggest/discover")
async def admin_discover_topics():
    """
    Automatically discover topics from web sources (admin only).

    Uses Tavily web search to find recent Christian apologetics content,
    extracts factual claims using LLM, deduplicates against existing
    claim cards, and adds novel topics to the generation queue.

    No request body required - this endpoint performs automatic discovery.

    Returns:
        Discovery summary:
            - extracted: Number of topics extracted from search results
            - added: Number of topics added to queue
            - skipped_duplicates: Number skipped due to existing similar claims
            - failed: Number that failed to add
            - sources_searched: Number of web sources searched

    Raises:
        HTTPException: If discovery fails or Tavily not configured
    """
    try:
        result = await autosuggest_service.discover_topics_from_web()

        return {
            "success": True,
            "message": f"Discovered {result['extracted']} topics from {result['sources_searched']} sources, added {result['added']} to queue",
            "extracted": result["extracted"],
            "added": result["added"],
            "skipped_duplicates": result["skipped_duplicates"],
            "failed": result["failed"],
            "sources_searched": result["sources_searched"],
        }

    except AutoSuggestServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"Error running auto-suggest discovery: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to run auto-suggest discovery")


# Review Workflow API endpoints (Phase 3.4)
@app.get("/api/admin/review/pending")
async def admin_get_pending_reviews(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get blog posts pending review (admin only).

    Returns topics with review_status='pending_review' along with
    their associated blog posts and claim cards.

    Args:
        skip: Offset for pagination (default: 0)
        limit: Number of records to return (default: 20, max: 100)
        db: Database session

    Returns:
        List of pending reviews with blog post and claim card details

    Raises:
        HTTPException: If query fails
    """
    try:
        review_service = ReviewService(db)
        result = await review_service.get_pending_reviews(skip=skip, limit=limit)
        return result

    except Exception as e:
        print(f"Error fetching pending reviews: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch pending reviews")


@app.post("/api/admin/review/{topic_id}/approve")
async def admin_approve_blog_post(
    topic_id: UUID,
    request: ReviewApproveRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Approve and publish blog post (admin only).

    Sets blog_posts.published_at = NOW() and updates review status.
    Blog article becomes visible in Read page.

    Args:
        topic_id: Topic queue ID
        request: JSON body containing:
            - reviewed_by: Admin username who reviewed
            - review_notes: Optional admin notes
        db: Database session

    Returns:
        Approval result with blog post ID and published timestamp

    Raises:
        HTTPException: If topic not found or approval fails
    """
    try:
        review_service = ReviewService(db)
        result = await review_service.approve_blog_post(
            topic_id=topic_id,
            reviewed_by=request.reviewed_by,
            review_notes=request.review_notes
        )
        return result

    except ReviewServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error approving blog post: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to approve blog post")


@app.post("/api/admin/review/{topic_id}/reject")
async def admin_reject_blog_post(
    topic_id: UUID,
    request: ReviewRejectRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reject blog post (admin only).

    Blog post NOT published (won't appear in Read page).
    Claim cards remain in database (still in Audits, still usable in chat).

    Args:
        topic_id: Topic queue ID
        request: JSON body containing:
            - reviewed_by: Admin username who reviewed
            - admin_feedback: Reason for rejection
        db: Database session

    Returns:
        Rejection result

    Raises:
        HTTPException: If topic not found or rejection fails
    """
    try:
        review_service = ReviewService(db)
        result = await review_service.reject_blog_post(
            topic_id=topic_id,
            reviewed_by=request.reviewed_by,
            admin_feedback=request.admin_feedback
        )
        return result

    except ReviewServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error rejecting blog post: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reject blog post")


@app.post("/api/admin/review/{topic_id}/revision")
async def admin_request_revision(
    topic_id: UUID,
    request: ReviewRevisionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request revision with selective re-run (admin only).

    Admin specifies which component to re-run:
    - "decomposer": Re-decompose topic into component claims
    - "claim_pipeline": Re-run specific claim card(s) through 5-agent pipeline
    - "composer": Re-run blog composer (title + article body)

    Args:
        topic_id: Topic queue ID
        request: JSON body containing:
            - reviewed_by: Admin username who reviewed
            - admin_feedback: Admin's revision instructions
            - revision_scope: What to re-run (decomposer/claim_pipeline/composer)
            - revision_details: Additional details (e.g., which claim_card_ids to re-run)
        db: Database session

    Returns:
        Revision result with execution details

    Raises:
        HTTPException: If topic not found, invalid scope, or revision fails
    """
    try:
        review_service = ReviewService(db)
        result = await review_service.request_revision(
            topic_id=topic_id,
            reviewed_by=request.reviewed_by,
            admin_feedback=request.admin_feedback,
            revision_scope=request.revision_scope,
            revision_details=request.revision_details
        )
        return result

    except ReviewServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error requesting revision: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to request revision")


@app.post("/api/admin/database/reset")
async def admin_database_reset(
    request: DatabaseResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Clear database (delete content, preserve system config) - admin only.

    Deletes all generated content while preserving system configuration:

    **Deleted:**
    - All claim cards (cascades to sources, apologetics_tags, category_tags)
    - All blog posts
    - All topics in queue
    - All router decisions

    **Preserved:**
    - Agent prompts (system configuration)
    - Agent configs (LLM models, settings)
    - Verified sources library (verified_sources table)

    Args:
        request: JSON body with "confirm": true
        db: Database session

    Returns:
        Summary of deleted records

    Raises:
        HTTPException: If confirmation not provided or deletion fails
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required: set 'confirm' to true"
        )

    try:
        from database.models import (
            ClaimCard, BlogPost, TopicQueue, RouterDecision,
            Source, ApologeticsTag, CategoryTag
        )

        # Count records before deletion
        claim_count_result = await db.execute(select(func.count()).select_from(ClaimCard))
        claim_count = claim_count_result.scalar_one()

        blog_count_result = await db.execute(select(func.count()).select_from(BlogPost))
        blog_count = blog_count_result.scalar_one()

        topic_count_result = await db.execute(select(func.count()).select_from(TopicQueue))
        topic_count = topic_count_result.scalar_one()

        router_count_result = await db.execute(select(func.count()).select_from(RouterDecision))
        router_count = router_count_result.scalar_one()

        # Delete in transaction (all or nothing)
        # Order matters: delete children before parents where FK constraints exist

        # 1. Delete router decisions (no dependencies)
        await db.execute(RouterDecision.__table__.delete())

        # 2. Delete blog posts (references topic_queue with SET NULL FK)
        await db.execute(BlogPost.__table__.delete())

        # 3. Delete claim card children (FK to claim_cards)
        await db.execute(Source.__table__.delete())
        await db.execute(ApologeticsTag.__table__.delete())
        await db.execute(CategoryTag.__table__.delete())

        # 4. Delete claim cards (now safe, all FK references removed)
        await db.execute(ClaimCard.__table__.delete())

        # 5. Delete topic queue (now safe, blog_post_id will be NULL)
        await db.execute(TopicQueue.__table__.delete())

        # Commit transaction
        await db.commit()

        return {
            "success": True,
            "message": "Database reset successfully",
            "deleted": {
                "claim_cards": claim_count,
                "blog_posts": blog_count,
                "topics": topic_count,
                "router_decisions": router_count,
            },
            "preserved": [
                "agent_prompts",
                "verified_sources (library)",
            ]
        }

    except Exception as e:
        await db.rollback()
        print(f"Error resetting database: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to reset database: {str(e)}")


# ============================================================================
# PUBLIC ENDPOINTS - Read Page & Audits Page (Phase 3.5)
# ============================================================================

@app.get("/api/blog/posts")
async def list_blog_posts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    List published blog posts for Read page.

    Public endpoint - only returns published articles (published_at NOT NULL).

    Args:
        skip: Offset for pagination (default: 0)
        limit: Number of records to return (default: 20, max: 100)
        db: Database session

    Returns:
        JSON with posts array, total count, and has_more flag
    """
    repo = BlogPostRepository(db)

    # Get published posts only
    posts = await repo.get_all(skip=skip, limit=limit, published_only=True)
    total = await repo.count(published_only=True)

    return {
        "posts": [
            {
                "id": str(post.id),
                "title": post.title,
                "article_body": post.article_body,
                "claim_card_ids": [str(cid) for cid in post.claim_card_ids],
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "created_at": post.created_at.isoformat(),
            }
            for post in posts
        ],
        "total": total,
        "has_more": skip + len(posts) < total,
    }


@app.get("/api/blog/posts/{post_id}")
async def get_blog_post(
    post_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single blog post by ID for Read page.

    Public endpoint - only returns if published.

    Args:
        post_id: Blog post UUID
        db: Database session

    Returns:
        Blog post detail with all fields

    Raises:
        HTTPException: 404 if post not found or not published
    """
    repo = BlogPostRepository(db)
    post = await repo.get_by_id(post_id)

    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    if not post.published_at:
        raise HTTPException(status_code=404, detail="Blog post not published")

    return {
        "id": str(post.id),
        "title": post.title,
        "article_body": post.article_body,
        "claim_card_ids": [str(cid) for cid in post.claim_card_ids],
        "published_at": post.published_at.isoformat(),
        "created_at": post.created_at.isoformat(),
    }


@app.get("/api/audits/cards")
async def list_audit_cards(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    category: Optional[str] = Query(None, description="Filter by category name"),
    verdict: Optional[str] = Query(None, description="Filter by verdict (True, False, Misleading, etc.)"),
    search: Optional[str] = Query(None, description="Text search on claim_text"),
    db: AsyncSession = Depends(get_db)
):
    """
    List claim cards for Audits page.

    Public endpoint - returns all cards where visible_in_audits = TRUE.
    Supports pagination and filtering by category, verdict, and text search.

    Args:
        skip: Offset for pagination (default: 0)
        limit: Number of records to return (default: 50, max: 100)
        category: Optional category filter (Genesis, Canon, Doctrine, etc.)
        verdict: Optional verdict filter (True, False, Misleading, etc.)
        search: Optional text search on claim_text (case-insensitive)
        db: Database session

    Returns:
        JSON with claim_cards array, total count, and has_more flag
    """
    repo = ClaimCardRepository(db)

    # Get visible claim cards with filters
    claim_cards = await repo.get_all(
        skip=skip,
        limit=limit,
        visible_in_audits=True,
        category=category,
        verdict=verdict,
        search=search
    )

    total = await repo.count(
        visible_in_audits=True,
        category=category,
        verdict=verdict,
        search=search
    )

    return {
        "claim_cards": [
            {
                "id": str(cc.id),
                "claim_text": cc.claim_text,
                "claimant": cc.claimant,
                "claim_type": cc.claim_type,
                "verdict": cc.verdict.value,
                "short_answer": cc.short_answer,
                "deep_answer": cc.deep_answer,
                "why_persists": cc.why_persists,
                "confidence_level": cc.confidence_level.value,
                "confidence_explanation": cc.confidence_explanation,
                "created_at": cc.created_at.isoformat(),
                "category_tags": [
                    {
                        "id": str(ct.id),
                        "category_name": ct.category_name,
                        "description": ct.description,
                    }
                    for ct in cc.category_tags
                ],
                "sources": [
                    {
                        "id": str(s.id),
                        "source_type": s.source_type.value,
                        "citation": s.citation,
                        "url": s.url,
                        "quote_text": s.quote_text,
                        "usage_context": s.usage_context,
                    }
                    for s in cc.sources
                ],
                "apologetics_tags": [
                    {
                        "id": str(at.id),
                        "technique_name": at.technique_name,
                        "description": at.description,
                    }
                    for at in cc.apologetics_tags
                ],
            }
            for cc in claim_cards
        ],
        "total": total,
        "has_more": skip + len(claim_cards) < total,
    }


@app.get("/api/audits/cards/{card_id}")
async def get_audit_card(
    card_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single claim card by ID for Audits page.

    Public endpoint - only returns if visible_in_audits = TRUE.

    Args:
        card_id: Claim card UUID
        db: Database session

    Returns:
        Claim card detail with all relationships (sources, tags, etc.)

    Raises:
        HTTPException: 404 if card not found or not visible
    """
    repo = ClaimCardRepository(db)
    claim_card = await repo.get_by_id(card_id)

    if not claim_card:
        raise HTTPException(status_code=404, detail="Claim card not found")

    if not claim_card.visible_in_audits:
        raise HTTPException(status_code=404, detail="Claim card not visible in audits")

    return {
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


@app.get("/api/public/sources")
async def list_public_sources(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all sources sorted by reference count (public endpoint).

    Returns sources with usage counts (number of claim cards referencing each source),
    sorted by most referenced first.

    Args:
        skip: Offset for pagination (default: 0)
        limit: Number of records to return (default: 50, max: 100)
        verification_status: Optional filter by verification_status
        source_type: Optional filter by source_type
        db: Database session

    Returns:
        JSON with sources array and pagination info
    """
    try:
        from database.models import Source

        # Build query: SELECT sources.*, COUNT(DISTINCT claim_card_id) as usage_count
        query = (
            select(
                Source,
                func.count().label("usage_count")
            )
            .group_by(Source.id)
            .order_by(func.count().desc(), Source.created_at.desc())
        )

        # Apply filters
        if verification_status:
            query = query.where(Source.verification_status == verification_status)
        if source_type:
            query = query.where(Source.source_type == source_type)

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Execute query
        result = await db.execute(query)
        rows = result.all()

        # Format response
        sources = [
            {
                "id": str(row.Source.id),
                "citation": row.Source.citation,
                "source_type": row.Source.source_type.value,
                "url": row.Source.url,
                "verification_method": row.Source.verification_method,
                "verification_status": row.Source.verification_status,
                "content_type": row.Source.content_type,
                "url_verified": row.Source.url_verified,
                "usage_count": row.usage_count,
                "created_at": row.Source.created_at.isoformat(),
            }
            for row in rows
        ]

        return {
            "sources": sources,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "count": len(sources),
            }
        }

    except Exception as e:
        print(f"Error fetching sources: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to fetch sources")


@app.get("/api/public/metrics")
async def get_public_metrics(db: AsyncSession = Depends(get_db)):
    """
    Get public metrics for home page.

    Public endpoint - returns counts for claims, blog posts, and questions answered.

    Returns:
        JSON with:
            - claim_count: Total number of claim cards
            - blog_count: Total number of published blog posts
            - question_count: Total number of questions answered (approximated by routing decisions)
    """
    try:
        claim_repo = ClaimCardRepository(db)
        blog_repo = BlogPostRepository(db)

        # Get counts
        claim_count = await claim_repo.count()
        blog_count = await blog_repo.count(published_only=True)

        # Question count: Count routing decisions as proxy for questions answered
        from database.models import RouterDecision
        question_result = await db.execute(
            select(func.count()).select_from(RouterDecision)
        )
        question_count = question_result.scalar_one()

        return {
            "claim_count": claim_count,
            "blog_count": blog_count,
            "question_count": question_count,
        }

    except Exception as e:
        print(f"Error fetching public metrics: {str(e)}")
        # Return zeros instead of failing
        return {
            "claim_count": 0,
            "blog_count": 0,
            "question_count": 0,
        }


@app.get("/api/public/graph")
async def get_knowledge_graph(db: AsyncSession = Depends(get_db)):
    """
    Get knowledge graph data for visualization.

    Public endpoint - returns nodes (blogs, claims, sources) and edges
    showing relationships between them.

    Returns:
        JSON with:
            - nodes: Array of {id, label, type, metadata}
            - edges: Array of {id, source, target, type}
    """
    try:
        from database.models import BlogPost, ClaimCard, Source

        # Get published blog posts
        blog_repo = BlogPostRepository(db)
        blogs = await blog_repo.get_all(skip=0, limit=100, published_only=True)

        print(f"[GRAPH DEBUG] Found {len(blogs)} published blogs")

        # Get all claim cards referenced by blogs
        all_claim_ids = set()
        for blog in blogs:
            print(f"[GRAPH DEBUG] Blog '{blog.title}' has {len(blog.claim_card_ids)} claims: {blog.claim_card_ids}")
            all_claim_ids.update(blog.claim_card_ids)

        print(f"[GRAPH DEBUG] Total unique claim IDs: {len(all_claim_ids)}")

        # Fetch claim cards
        claim_repo = ClaimCardRepository(db)
        claims_dict = {}
        for claim_id in all_claim_ids:
            # Convert to UUID if it's a string
            from uuid import UUID as UUIDType
            if isinstance(claim_id, str):
                claim_id_obj = UUIDType(claim_id)
            else:
                claim_id_obj = claim_id

            claim = await claim_repo.get_by_id(claim_id_obj)
            if claim:
                claims_dict[str(claim_id_obj)] = claim
            else:
                print(f"[GRAPH DEBUG] Claim not found: {claim_id_obj}")

        print(f"[GRAPH DEBUG] Successfully fetched {len(claims_dict)} claims")

        # Build nodes and edges
        nodes = []
        edges = []

        # Add blog nodes
        for blog in blogs:
            nodes.append({
                "id": f"blog-{blog.id}",
                "label": blog.title[:50] + "..." if len(blog.title) > 50 else blog.title,
                "type": "blog",
                "metadata": {
                    "title": blog.title,
                    "published_at": blog.published_at.isoformat() if blog.published_at else None,
                }
            })

            # Add edges from blog to claims
            for claim_id in blog.claim_card_ids:
                if str(claim_id) in claims_dict:
                    edges.append({
                        "id": f"blog-{blog.id}-claim-{claim_id}",
                        "source": f"blog-{blog.id}",
                        "target": f"claim-{claim_id}",
                        "type": "HAS_CLAIM"
                    })

        # Add claim nodes and edges to sources
        for claim_id_str, claim in claims_dict.items():
            nodes.append({
                "id": f"claim-{claim.id}",
                "label": claim.claim_text[:50] + "..." if len(claim.claim_text) > 50 else claim.claim_text,
                "type": "claim",
                "metadata": {
                    "claim_text": claim.claim_text,
                    "verdict": claim.verdict.value,
                }
            })

            # Add source nodes and edges
            for source in claim.sources:
                source_id = f"source-{source.id}"

                # Add source node if not already added
                if not any(n["id"] == source_id for n in nodes):
                    nodes.append({
                        "id": source_id,
                        "label": source.citation[:50] + "..." if len(source.citation) > 50 else source.citation,
                        "type": "source",
                        "metadata": {
                            "citation": source.citation,
                            "source_type": source.source_type.value,
                            "url": source.url,
                        }
                    })

                # Add edge from claim to source
                edges.append({
                    "id": f"claim-{claim.id}-source-{source.id}",
                    "source": f"claim-{claim.id}",
                    "target": source_id,
                    "type": "USES_SOURCE"
                })

        print(f"[GRAPH DEBUG] Returning {len(nodes)} nodes and {len(edges)} edges")

        return {
            "nodes": nodes,
            "edges": edges
        }

    except Exception as e:
        print(f"Error fetching knowledge graph: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to fetch knowledge graph")


# ============================================================================
# TESTING & DEBUGGING ENDPOINTS
# ============================================================================

@app.post("/api/pipeline/test")
async def test_pipeline(
    request: PipelineTestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Test endpoint for the 5-agent pipeline.

    Accepts a question and runs it through the complete pipeline:
    1. TopicFinderAgent
    2. SourceCheckerAgent
    3. AdversarialCheckerAgent
    4. WritingAgent
    5. PublisherAgent

    Returns structured output from all agents with execution details.
    Does NOT save to database - this is for testing pipeline flow only.

    Args:
        request: JSON body containing "question" field
        db: Database session

    Returns:
        Complete pipeline result including:
        - success: Whether pipeline completed successfully
        - question: Original question
        - pipeline_start/end: Execution timestamps
        - pipeline_duration_seconds: Total execution time
        - agents: List of agent results in order
        - claim_card_data: Aggregated data (not saved to DB)
        - error: Error message if pipeline failed

    Raises:
        HTTPException: If pipeline encounters unexpected error
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        orchestrator = PipelineOrchestrator(db)
        result = await orchestrator.run_pipeline(
            question=request.question,
            websocket_session_id=request.websocket_session_id,
            connection_manager=manager if request.websocket_session_id else None
        )
        return result

    except PipelineError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error in pipeline: {str(e)}"
        )


@app.websocket("/ws/pipeline/{session_id}")
async def websocket_pipeline_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time pipeline progress updates.

    Client connects with a session_id, then triggers pipeline execution
    via POST /api/pipeline/test with the same session_id.
    Pipeline will send progress updates through this WebSocket connection.

    Args:
        websocket: WebSocket connection
        session_id: Unique session identifier (UUID from frontend)
    """
    await manager.connect(session_id, websocket)
    try:
        # Keep connection open, waiting for messages or disconnect
        while True:
            # Receive any messages from client (can be used for ping/pong)
            data = await websocket.receive_text()
            # Echo back for testing (optional)
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        print(f"WebSocket disconnected: {session_id}")
        manager.disconnect(session_id)
    except Exception as e:
        print(f"WebSocket error for session {session_id}: {str(e)}")
        manager.disconnect(session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.SERVICE_HOST,
        port=settings.SERVICE_PORT,
        reload=True,
    )
