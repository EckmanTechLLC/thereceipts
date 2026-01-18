"""
SQLAlchemy models for TheReceipts database.

Schema designed per ADR 001 - Core Architecture & System Design.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Enum, Float, ARRAY, JSON, Index, Boolean
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
import enum
import uuid


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class VerdictEnum(str, enum.Enum):
    """Verdict categories for claim analysis."""
    TRUE = "True"
    MISLEADING = "Misleading"
    FALSE = "False"
    UNFALSIFIABLE = "Unfalsifiable"
    DEPENDS_ON_DEFINITIONS = "Depends on Definitions"


class ConfidenceLevelEnum(str, enum.Enum):
    """Confidence levels for claim verdicts."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SourceTypeEnum(str, enum.Enum):
    """Types of sources for claim verification."""
    PRIMARY_HISTORICAL = "primary historical"
    SCHOLARLY_PEER_REVIEWED = "scholarly peer-reviewed"


class TopicStatusEnum(str, enum.Enum):
    """Status of topics in the generation queue."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatusEnum(str, enum.Enum):
    """Review status for blog post generation workflow."""
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class RoutingModeEnum(str, enum.Enum):
    """Routing modes for Router Agent decisions."""
    EXACT_MATCH = "EXACT_MATCH"
    CONTEXTUAL = "CONTEXTUAL"
    NOVEL_CLAIM = "NOVEL_CLAIM"


class ClaimCard(Base):
    """
    Core entity representing an audited claim.

    Each claim card is generated through the 5-agent pipeline and
    serves as the knowledge base for both chat and blog modes.
    """
    __tablename__ = "claim_cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Core claim fields
    claim_text = Column(Text, nullable=False)
    claimant = Column(String(500), nullable=False)  # Author/org who made the claim
    claim_type = Column(String(100), nullable=True)  # history, science, doctrine, translation, etc.
    claim_type_category = Column(Text, nullable=True)  # historical, epistemology, interpretation, etc.

    # Verdict
    verdict = Column(Enum(VerdictEnum), nullable=False)

    # Answers
    short_answer = Column(Text, nullable=False)  # ≤150 words plain-language summary
    deep_answer = Column(Text, nullable=False)  # Full detailed analysis

    # Why this claim persists
    why_persists = Column(JSONB, nullable=True)  # Array of reasons (psychological/social/institutional)

    # Confidence
    confidence_level = Column(Enum(ConfidenceLevelEnum), nullable=False)
    confidence_explanation = Column(Text, nullable=False)

    # Agent audit trail (full pipeline execution trace)
    agent_audit = Column(JSONB, nullable=False)

    # Semantic search embedding (1536 dimensions for OpenAI ada-002)
    embedding = Column(Vector(1536), nullable=True)

    # Visibility in Audits page (Phase 3: Auto-Blog)
    visible_in_audits = Column(Boolean, default=True, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    sources = relationship("Source", back_populates="claim_card", cascade="all, delete-orphan")
    apologetics_tags = relationship("ApologeticsTag", back_populates="claim_card", cascade="all, delete-orphan")
    category_tags = relationship("CategoryTag", back_populates="claim_card", cascade="all, delete-orphan")

    # Indexes for search
    __table_args__ = (
        Index('ix_claim_cards_claim_text', 'claim_text'),
        Index('ix_claim_cards_claimant', 'claimant'),
        Index('ix_claim_cards_verdict', 'verdict'),
        Index('ix_claim_cards_created_at', 'created_at'),
    )


class Source(Base):
    """
    Sources supporting claim card verdicts.

    Separated by type: primary historical sources vs scholarly peer-reviewed sources.
    Phase 4.1: Added verification metadata for API-verified sources.
    """
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_card_id = Column(UUID(as_uuid=True), ForeignKey("claim_cards.id"), nullable=False)

    source_type = Column(Enum(SourceTypeEnum), nullable=False)
    citation = Column(Text, nullable=False)  # Full citation
    url = Column(Text, nullable=True)  # Link if available
    quote_text = Column(Text, nullable=True)  # Relevant quote from source
    usage_context = Column(Text, nullable=True)  # How this source is used in the analysis

    # Phase 4.1: Verification metadata
    verification_method = Column(String(50), nullable=True)  # google_books, semantic_scholar, tavily, llm_unverified
    verification_status = Column(String(50), nullable=True)  # verified, partially_verified, unverified
    content_type = Column(String(50), nullable=True)  # exact_quote, verified_paraphrase, unverified_content
    url_verified = Column(Boolean, default=False, nullable=False)  # URL tested and working

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    claim_card = relationship("ClaimCard", back_populates="sources")

    __table_args__ = (
        Index('ix_sources_claim_card_id', 'claim_card_id'),
        Index('ix_sources_source_type', 'source_type'),
        Index('ix_sources_verification_method', 'verification_method'),
        Index('ix_sources_verification_status', 'verification_status'),
    )


class VerifiedSource(Base):
    """
    Verified Source Library (Tier 0) for reusable source metadata.

    Phase 4.1: Library of API-verified sources (books, papers, ancient texts).
    Stores book/paper metadata with embeddings for semantic search.
    Reuses verified metadata across claim cards, but quotes are claim-specific.
    """
    __tablename__ = "verified_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source identification
    source_type = Column(String(50), nullable=False)  # book, paper, ancient_text
    title = Column(String(1000), nullable=False)
    author = Column(String(500), nullable=False)

    # Publication metadata
    publisher = Column(String(500), nullable=True)
    publication_date = Column(String(100), nullable=True)
    isbn = Column(String(50), nullable=True)
    doi = Column(String(200), nullable=True)

    # Verification data
    url = Column(Text, nullable=False)  # Verified working URL
    content_snippet = Column(Text, nullable=True)  # Sample content from source
    topic_keywords = Column(ARRAY(String), nullable=True)  # Keywords for semantic search

    # Semantic search embedding (1536 dimensions for OpenAI ada-002)
    embedding = Column(Vector(1536), nullable=True)

    # Verification metadata
    verification_method = Column(String(50), nullable=False)  # google_books, semantic_scholar, ccel, perseus, tavily
    verification_status = Column(String(50), nullable=False)  # verified, partially_verified

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_verified_sources_source_type', 'source_type'),
        Index('ix_verified_sources_title', 'title'),
        Index('ix_verified_sources_author', 'author'),
    )


class ApologeticsTag(Base):
    """
    Tags identifying apologetics techniques used in claims.

    Examples: quote-mining, category error, false dichotomy, moving goalposts, etc.
    """
    __tablename__ = "apologetics_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_card_id = Column(UUID(as_uuid=True), ForeignKey("claim_cards.id"), nullable=False)

    technique_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)  # Explanation of how this technique was used

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    claim_card = relationship("ClaimCard", back_populates="apologetics_tags")

    __table_args__ = (
        Index('ix_apologetics_tags_claim_card_id', 'claim_card_id'),
        Index('ix_apologetics_tags_technique_name', 'technique_name'),
    )


class CategoryTag(Base):
    """
    Tags for broad UI navigation categories.

    Implements dual categorization per ADR 001:
    - claim_type (technical, flexible)
    - category_tags (broad UI navigation: Genesis, Canon, Doctrine, Ethics, Institutions)

    Multiple categories per claim allowed for flexible navigation.
    """
    __tablename__ = "category_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_card_id = Column(UUID(as_uuid=True), ForeignKey("claim_cards.id"), nullable=False)

    category_name = Column(String(200), nullable=False)  # Genesis, Canon, Doctrine, Ethics, Institutions, etc.
    description = Column(Text, nullable=True)  # Optional explanation of why this category applies

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    claim_card = relationship("ClaimCard", back_populates="category_tags")

    __table_args__ = (
        Index('ix_category_tags_claim_card_id', 'claim_card_id'),
        Index('ix_category_tags_category_name', 'category_name'),
    )


class AgentPrompt(Base):
    """
    Editable LLM configurations for each agent in the pipeline.

    Stored in database so prompts can be adjusted without code changes.
    """
    __tablename__ = "agent_prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    agent_name = Column(String(100), nullable=False, unique=True)  # topic_finder, source_checker, etc.
    llm_provider = Column(String(50), nullable=False)  # anthropic, openai, etc.
    model_name = Column(String(100), nullable=False)  # claude-3-opus, gpt-4, etc.
    system_prompt = Column(Text, nullable=False)

    # LLM parameters
    temperature = Column(Float, default=0.7, nullable=False)
    max_tokens = Column(Integer, default=4096, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_agent_prompts_agent_name', 'agent_name'),
    )


class TopicQueue(Base):
    """
    Queue of topics/claims to audit for auto-blog generation.

    Supports both manual additions and auto-suggest from LLM+web search.
    """
    __tablename__ = "topic_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    topic_text = Column(Text, nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # Higher = process sooner
    status = Column(Enum(TopicStatusEnum), default=TopicStatusEnum.QUEUED, nullable=False)
    source = Column(String(500), nullable=True)  # Where this topic came from (manual, auto-suggest, etc.)

    # Generated claim card IDs (array of UUIDs as strings)
    claim_card_ids = Column(ARRAY(String), nullable=True)

    # Scheduling
    scheduled_for = Column(DateTime, nullable=True)

    # Error tracking for failed topics
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    # Review workflow (Phase 3: Auto-Blog)
    review_status = Column(String(50), default="pending_review", nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    admin_feedback = Column(Text, nullable=True)
    blog_post_id = Column(UUID(as_uuid=True), ForeignKey("blog_posts.id", ondelete="SET NULL"), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_topic_queue_status', 'status'),
        Index('ix_topic_queue_priority', 'priority'),
        Index('ix_topic_queue_scheduled_for', 'scheduled_for'),
        Index('ix_topic_queue_review_status', 'review_status'),
    )


class RouterDecision(Base):
    """
    Tracks routing decisions made by Router Agent.

    Used for debugging, tuning prompts, and analyzing routing patterns.
    Part of Phase 3 intelligent routing system (ADR 002).
    """
    __tablename__ = "router_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Question context
    question_text = Column(Text, nullable=False)  # Original user question
    reformulated_question = Column(Text, nullable=False)  # From Context Analyzer
    conversation_context = Column(JSONB, nullable=True)  # Recent conversation history

    # Routing decision
    mode_selected = Column(Enum(RoutingModeEnum, name='routing_mode'), nullable=False)
    claim_cards_referenced = Column(ARRAY(UUID), nullable=True)  # Cards used in response

    # Tool execution trace
    search_candidates = Column(JSONB, nullable=True)  # Results from search_existing_claims
    reasoning = Column(Text, nullable=True)  # LLM's routing reasoning

    # Performance metrics
    response_time_ms = Column(Integer, nullable=False)  # Total routing time

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_router_decisions_mode_selected', 'mode_selected'),
        Index('ix_router_decisions_created_at', 'created_at'),
    )


class BlogPost(Base):
    """
    Blog articles synthesizing claim card findings into prose.

    Part of Phase 3 Auto-Blog system (ADR 003).
    Each blog post represents a topic that has been:
    1. Decomposed into component claims
    2. Analyzed through 5-agent pipeline (generating claim cards)
    3. Synthesized into cohesive narrative article
    4. Reviewed and approved by admin

    Blog posts appear in Read page when published_at is set.
    Component claim cards remain independently visible in Audits page.
    """
    __tablename__ = "blog_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Reference to originating topic
    topic_queue_id = Column(UUID(as_uuid=True), ForeignKey("topic_queue.id", ondelete="SET NULL"), nullable=True)

    # Article content
    title = Column(String(500), nullable=False)
    article_body = Column(Text, nullable=False)  # Full synthesized prose article

    # Component claim cards (array of UUIDs, referenced within article)
    claim_card_ids = Column(ARRAY(UUID), nullable=False)

    # Publication status
    published_at = Column(DateTime, nullable=True)  # NULL = not published, NOW() = published
    reviewed_by = Column(String(200), nullable=True)  # Admin username who reviewed
    review_notes = Column(Text, nullable=True)  # Admin notes from review

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_blog_posts_published_at', 'published_at'),
        Index('ix_blog_posts_topic_queue_id', 'topic_queue_id'),
    )
