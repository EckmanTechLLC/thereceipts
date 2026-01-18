"""
Repository pattern for database operations.

Provides clean abstraction over SQLAlchemy for common CRUD operations.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    ClaimCard, Source, ApologeticsTag, CategoryTag,
    AgentPrompt, TopicQueue, TopicStatusEnum, BlogPost, VerifiedSource
)


class ClaimCardRepository:
    """Repository for ClaimCard operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, claim_id: UUID) -> Optional[ClaimCard]:
        """Get a claim card by ID with all relationships loaded."""
        result = await self.session.execute(
            select(ClaimCard)
            .options(
                selectinload(ClaimCard.sources),
                selectinload(ClaimCard.apologetics_tags),
                selectinload(ClaimCard.category_tags),
            )
            .where(ClaimCard.id == claim_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        category: Optional[str] = None,
        visible_in_audits: Optional[bool] = None,
        verdict: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[ClaimCard]:
        """
        Get claim cards with pagination and optional filters.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            category: Optional category name to filter by
            visible_in_audits: Optional visibility filter (True for audits page)
            verdict: Optional verdict filter (True, False, Misleading, etc.)
            search: Optional text search on claim_text (case-insensitive)

        Returns:
            List of ClaimCard objects
        """
        query = (
            select(ClaimCard)
            .options(
                selectinload(ClaimCard.sources),
                selectinload(ClaimCard.apologetics_tags),
                selectinload(ClaimCard.category_tags),
            )
            .order_by(ClaimCard.created_at.desc())
        )

        # Apply visible_in_audits filter if provided
        if visible_in_audits is not None:
            query = query.where(ClaimCard.visible_in_audits == visible_in_audits)

        # Apply verdict filter if provided
        if verdict:
            from database.models import VerdictEnum
            query = query.where(ClaimCard.verdict == VerdictEnum(verdict))

        # Apply search filter if provided
        if search:
            query = query.where(ClaimCard.claim_text.ilike(f"%{search}%"))

        # Apply category filter if provided
        if category:
            query = query.join(ClaimCard.category_tags).where(
                CategoryTag.category_name == category
            )

        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().unique().all())

    async def count(
        self,
        category: Optional[str] = None,
        visible_in_audits: Optional[bool] = None,
        verdict: Optional[str] = None,
        search: Optional[str] = None
    ) -> int:
        """
        Count claim cards matching filters.

        Args:
            category: Optional category name to filter by
            visible_in_audits: Optional visibility filter
            verdict: Optional verdict filter
            search: Optional text search on claim_text

        Returns:
            Total count of matching claim cards
        """
        query = select(func.count()).select_from(ClaimCard)

        # Apply visible_in_audits filter if provided
        if visible_in_audits is not None:
            query = query.where(ClaimCard.visible_in_audits == visible_in_audits)

        # Apply verdict filter if provided
        if verdict:
            from database.models import VerdictEnum
            query = query.where(ClaimCard.verdict == VerdictEnum(verdict))

        # Apply search filter if provided
        if search:
            query = query.where(ClaimCard.claim_text.ilike(f"%{search}%"))

        # Apply category filter if provided
        if category:
            query = query.join(ClaimCard.category_tags).where(
                CategoryTag.category_name == category
            )

        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, claim_card: ClaimCard) -> ClaimCard:
        """Create a new claim card."""
        self.session.add(claim_card)
        await self.session.flush()
        await self.session.refresh(claim_card)
        return claim_card

    async def update(self, claim_card: ClaimCard) -> ClaimCard:
        """Update an existing claim card."""
        await self.session.flush()
        await self.session.refresh(claim_card)
        return claim_card

    async def delete(self, claim_id: UUID) -> bool:
        """Delete a claim card by ID."""
        claim_card = await self.get_by_id(claim_id)
        if claim_card:
            await self.session.delete(claim_card)
            await self.session.flush()
            return True
        return False

    async def search_by_embedding(
        self,
        embedding: List[float],
        threshold: float = 0.85,
        limit: int = 5,
        exclude_claim_ids: Optional[List[UUID]] = None
    ) -> List[tuple[ClaimCard, float]]:
        """
        Search for similar claim cards using vector similarity.

        Uses pgvector's cosine similarity operator (<=>).
        Lower distance = higher similarity.

        Args:
            embedding: Query embedding vector (1536 dimensions)
            threshold: Minimum similarity threshold (0-1, default 0.85)
            limit: Maximum number of results to return
            exclude_claim_ids: Optional list of claim IDs to exclude from results
                               (useful for intra-blog deduplication)

        Returns:
            List of tuples: (ClaimCard, similarity_score)
            Ordered by similarity (highest first)
        """
        from sqlalchemy import text

        # pgvector cosine distance: 0 = identical, 2 = opposite
        # Convert to similarity: similarity = 1 - (distance / 2)
        # Threshold of 0.85 similarity = 0.3 distance
        distance_threshold = (1 - threshold) * 2

        # Build WHERE clause with optional exclusion
        where_clauses = [
            "c.embedding IS NOT NULL",
            "(c.embedding <=> :query_embedding) <= :distance_threshold"
        ]

        params = {
            "query_embedding": str(embedding),
            "distance_threshold": distance_threshold,
            "limit": limit
        }

        # Add exclusion filter if provided
        if exclude_claim_ids:
            # Convert UUIDs to strings for SQL array comparison
            exclude_ids_str = [str(cid) for cid in exclude_claim_ids]
            where_clauses.append("c.id::text != ALL(:exclude_ids)")
            params["exclude_ids"] = exclude_ids_str

        where_clause = " AND ".join(where_clauses)

        # Build query with pgvector operator
        # Note: <=> is cosine distance operator
        query = text(f"""
            SELECT
                c.*,
                1 - (c.embedding <=> :query_embedding) / 2 as similarity
            FROM claim_cards c
            WHERE {where_clause}
            ORDER BY c.embedding <=> :query_embedding
            LIMIT :limit
        """)

        result = await self.session.execute(query, params)

        rows = result.fetchall()

        # Load full ClaimCard objects with relationships
        claim_cards_with_scores = []
        for row in rows:
            claim_card = await self.get_by_id(row[0])  # row[0] is the id
            similarity = row[-1]  # Last column is similarity
            if claim_card:
                claim_cards_with_scores.append((claim_card, similarity))

        return claim_cards_with_scores

    async def upsert_embedding(
        self,
        claim_card_id: UUID,
        embedding: List[float]
    ) -> bool:
        """
        Update or insert embedding for a claim card.

        Args:
            claim_card_id: ID of the claim card
            embedding: Embedding vector (1536 dimensions)

        Returns:
            True if successful, False if claim card not found
        """
        claim_card = await self.get_by_id(claim_card_id)
        if not claim_card:
            return False

        claim_card.embedding = embedding
        await self.session.flush()
        return True

    async def create_from_pipeline_output(
        self,
        pipeline_data: dict,
        question: str
    ) -> ClaimCard:
        """
        Create claim card from pipeline output with all relationships.

        Takes structured output from PipelineOrchestrator and creates
        ClaimCard with Sources, ApologeticsTags, and CategoryTags.

        Args:
            pipeline_data: Dictionary from pipeline containing:
                - claim_text, claimant, claim_type, verdict
                - short_answer, deep_answer, why_persists
                - confidence_level, confidence_explanation
                - primary_sources, scholarly_sources (arrays)
                - apologetics_techniques (array)
                - category_tags (array)
                - audit_summary, limitations, change_verdict_if
            question: Original user question (for audit trail)

        Returns:
            Created ClaimCard with all relationships

        Raises:
            ValueError: If required fields are missing
        """
        from database.models import (
            ClaimCard, Source, ApologeticsTag, CategoryTag,
            VerdictEnum, ConfidenceLevelEnum, SourceTypeEnum
        )

        # Validate required fields
        required_fields = [
            "claim_text", "claimant", "verdict",
            "short_answer", "deep_answer", "confidence_level"
        ]
        missing_fields = [f for f in required_fields if not pipeline_data.get(f)]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # Validate verdict is a valid enum value
        try:
            VerdictEnum(pipeline_data.get("verdict"))
        except ValueError:
            raise ValueError(f"Invalid verdict value: {pipeline_data.get('verdict')}")

        # Validate confidence_level is a valid enum value
        try:
            ConfidenceLevelEnum(pipeline_data.get("confidence_level"))
        except ValueError:
            raise ValueError(f"Invalid confidence_level value: {pipeline_data.get('confidence_level')}")

        # Build agent_audit structure
        agent_audit = {
            "original_question": question,
            "audit_summary": pipeline_data.get("audit_summary", ""),
            "limitations": pipeline_data.get("limitations", []),
            "change_verdict_if": pipeline_data.get("change_verdict_if", ""),
        }

        # Create ClaimCard
        claim_card = ClaimCard(
            claim_text=pipeline_data.get("claim_text", ""),
            claimant=pipeline_data.get("claimant", ""),
            claim_type=pipeline_data.get("claim_type"),
            verdict=VerdictEnum(pipeline_data.get("verdict", "Unfalsifiable")),
            short_answer=pipeline_data.get("short_answer", ""),
            deep_answer=pipeline_data.get("deep_answer", ""),
            why_persists=pipeline_data.get("why_persists", []),
            confidence_level=ConfidenceLevelEnum(pipeline_data.get("confidence_level", "Medium")),
            confidence_explanation=pipeline_data.get("confidence_explanation", ""),
            agent_audit=agent_audit,
        )

        self.session.add(claim_card)
        await self.session.flush()

        # Create Sources - Primary Historical
        for source_data in pipeline_data.get("primary_sources", []):
            if isinstance(source_data, dict):
                source = Source(
                    claim_card_id=claim_card.id,
                    source_type=SourceTypeEnum.PRIMARY_HISTORICAL,
                    citation=source_data.get("citation", ""),
                    url=source_data.get("url"),
                    quote_text=source_data.get("quote_text") or source_data.get("quote"),
                    usage_context=source_data.get("usage_context"),
                    # Phase 4.1: Verification metadata
                    verification_method=source_data.get("verification_method"),
                    verification_status=source_data.get("verification_status"),
                    content_type=source_data.get("content_type"),
                    url_verified=source_data.get("url_verified", False),
                )
                self.session.add(source)

        # Create Sources - Scholarly Peer-Reviewed
        for source_data in pipeline_data.get("scholarly_sources", []):
            if isinstance(source_data, dict):
                source = Source(
                    claim_card_id=claim_card.id,
                    source_type=SourceTypeEnum.SCHOLARLY_PEER_REVIEWED,
                    citation=source_data.get("citation", ""),
                    url=source_data.get("url"),
                    quote_text=source_data.get("quote_text") or source_data.get("quote"),
                    usage_context=source_data.get("usage_context"),
                    # Phase 4.1: Verification metadata
                    verification_method=source_data.get("verification_method"),
                    verification_status=source_data.get("verification_status"),
                    content_type=source_data.get("content_type"),
                    url_verified=source_data.get("url_verified", False),
                )
                self.session.add(source)

        # Create ApologeticsTags
        for technique_data in pipeline_data.get("apologetics_techniques", []):
            if isinstance(technique_data, dict):
                tag = ApologeticsTag(
                    claim_card_id=claim_card.id,
                    technique_name=technique_data.get("technique_name", ""),
                    description=technique_data.get("description"),
                )
                self.session.add(tag)

        # Create CategoryTags
        for category_data in pipeline_data.get("category_tags", []):
            if isinstance(category_data, dict):
                tag = CategoryTag(
                    claim_card_id=claim_card.id,
                    category_name=category_data.get("category_name", ""),
                    description=category_data.get("description"),
                )
                self.session.add(tag)
            elif isinstance(category_data, str):
                # Handle simple string category names
                tag = CategoryTag(
                    claim_card_id=claim_card.id,
                    category_name=category_data,
                    description=None,
                )
                self.session.add(tag)

        await self.session.flush()
        await self.session.refresh(claim_card)

        return claim_card


class AgentPromptRepository:
    """Repository for AgentPrompt operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_agent_name(self, agent_name: str) -> Optional[AgentPrompt]:
        """Get an agent prompt by agent name."""
        result = await self.session.execute(
            select(AgentPrompt).where(AgentPrompt.agent_name == agent_name)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> List[AgentPrompt]:
        """Get all agent prompts."""
        result = await self.session.execute(
            select(AgentPrompt).order_by(AgentPrompt.agent_name)
        )
        return list(result.scalars().all())

    async def create(self, agent_prompt: AgentPrompt) -> AgentPrompt:
        """Create a new agent prompt."""
        self.session.add(agent_prompt)
        await self.session.flush()
        await self.session.refresh(agent_prompt)
        return agent_prompt

    async def update(self, agent_prompt: AgentPrompt) -> AgentPrompt:
        """Update an existing agent prompt."""
        await self.session.flush()
        await self.session.refresh(agent_prompt)
        return agent_prompt

    async def delete(self, agent_name: str) -> bool:
        """Delete an agent prompt by agent name."""
        agent_prompt = await self.get_by_agent_name(agent_name)
        if agent_prompt:
            await self.session.delete(agent_prompt)
            await self.session.flush()
            return True
        return False


class TopicQueueRepository:
    """Repository for TopicQueue operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, topic_id: UUID) -> Optional[TopicQueue]:
        """Get a topic by ID."""
        result = await self.session.execute(
            select(TopicQueue).where(TopicQueue.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[TopicStatusEnum] = None
    ) -> List[TopicQueue]:
        """
        Get topics with pagination and optional status filter.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status to filter by

        Returns:
            List of TopicQueue objects ordered by priority (descending)
        """
        query = select(TopicQueue).order_by(
            TopicQueue.priority.desc(),
            TopicQueue.created_at.asc()
        )

        if status:
            query = query.where(TopicQueue.status == status)

        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_next_queued(self) -> Optional[TopicQueue]:
        """Get the highest priority queued topic."""
        result = await self.session.execute(
            select(TopicQueue)
            .where(TopicQueue.status == TopicStatusEnum.QUEUED)
            .order_by(TopicQueue.priority.desc(), TopicQueue.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, topic: TopicQueue) -> TopicQueue:
        """Create a new topic in the queue."""
        self.session.add(topic)
        await self.session.flush()
        await self.session.refresh(topic)
        return topic

    async def update(self, topic: TopicQueue) -> TopicQueue:
        """Update an existing topic."""
        await self.session.flush()
        await self.session.refresh(topic)
        return topic

    async def delete(self, topic_id: UUID) -> bool:
        """Delete a topic by ID."""
        topic = await self.get_by_id(topic_id)
        if topic:
            await self.session.delete(topic)
            await self.session.flush()
            return True
        return False


class CategoryTagRepository:
    """Repository for CategoryTag operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_claim_id(self, claim_id: UUID) -> List[CategoryTag]:
        """Get all category tags for a specific claim card."""
        result = await self.session.execute(
            select(CategoryTag).where(CategoryTag.claim_card_id == claim_id)
        )
        return list(result.scalars().all())

    async def get_unique_categories(self) -> List[str]:
        """Get list of unique category names across all claim cards."""
        result = await self.session.execute(
            select(distinct(CategoryTag.category_name))
            .order_by(CategoryTag.category_name)
        )
        return list(result.scalars().all())

    async def create(self, category_tag: CategoryTag) -> CategoryTag:
        """Create a new category tag."""
        self.session.add(category_tag)
        await self.session.flush()
        await self.session.refresh(category_tag)
        return category_tag

    async def delete(self, tag_id: UUID) -> bool:
        """Delete a category tag by ID."""
        result = await self.session.execute(
            select(CategoryTag).where(CategoryTag.id == tag_id)
        )
        tag = result.scalar_one_or_none()
        if tag:
            await self.session.delete(tag)
            await self.session.flush()
            return True
        return False


class BlogPostRepository:
    """Repository for BlogPost operations (Phase 3: Auto-Blog)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, post_id: UUID) -> Optional[BlogPost]:
        """Get a blog post by ID."""
        result = await self.session.execute(
            select(BlogPost).where(BlogPost.id == post_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        published_only: bool = False
    ) -> List[BlogPost]:
        """
        Get blog posts with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            published_only: If True, only return published posts (published_at NOT NULL)

        Returns:
            List of BlogPost objects ordered by created_at (descending)
        """
        query = select(BlogPost).order_by(BlogPost.created_at.desc())

        if published_only:
            query = query.where(BlogPost.published_at.isnot(None))

        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_topic_queue_id(self, topic_queue_id: UUID) -> Optional[BlogPost]:
        """Get blog post associated with a topic queue entry."""
        result = await self.session.execute(
            select(BlogPost).where(BlogPost.topic_queue_id == topic_queue_id)
        )
        return result.scalar_one_or_none()

    async def count(self, published_only: bool = False) -> int:
        """
        Count blog posts.

        Args:
            published_only: If True, only count published posts

        Returns:
            Total count of matching blog posts
        """
        query = select(func.count()).select_from(BlogPost)

        if published_only:
            query = query.where(BlogPost.published_at.isnot(None))

        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, blog_post: BlogPost) -> BlogPost:
        """Create a new blog post."""
        self.session.add(blog_post)
        await self.session.flush()
        await self.session.refresh(blog_post)
        return blog_post

    async def update(self, blog_post: BlogPost) -> BlogPost:
        """Update an existing blog post."""
        await self.session.flush()
        await self.session.refresh(blog_post)
        return blog_post

    async def delete(self, post_id: UUID) -> bool:
        """Delete a blog post by ID."""
        blog_post = await self.get_by_id(post_id)
        if blog_post:
            await self.session.delete(blog_post)
            await self.session.flush()
            return True
        return False

    async def publish(
        self,
        post_id: UUID,
        reviewed_by: str,
        review_notes: Optional[str] = None
    ) -> Optional[BlogPost]:
        """
        Publish a blog post (set published_at timestamp).

        Args:
            post_id: Blog post ID
            reviewed_by: Admin username who approved
            review_notes: Optional review notes

        Returns:
            Updated BlogPost or None if not found
        """
        blog_post = await self.get_by_id(post_id)
        if not blog_post:
            return None

        blog_post.published_at = datetime.utcnow()
        blog_post.reviewed_by = reviewed_by
        if review_notes:
            blog_post.review_notes = review_notes

        await self.session.flush()
        await self.session.refresh(blog_post)
        return blog_post

    async def unpublish(self, post_id: UUID) -> Optional[BlogPost]:
        """
        Unpublish a blog post (set published_at to NULL).

        Args:
            post_id: Blog post ID

        Returns:
            Updated BlogPost or None if not found
        """
        blog_post = await self.get_by_id(post_id)
        if not blog_post:
            return None

        blog_post.published_at = None
        await self.session.flush()
        await self.session.refresh(blog_post)
        return blog_post


class VerifiedSourceRepository:
    """Repository for VerifiedSource operations (Phase 4.1: Source Verification Library)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, source_id: UUID) -> Optional[VerifiedSource]:
        """Get a verified source by ID."""
        result = await self.session.execute(
            select(VerifiedSource).where(VerifiedSource.id == source_id)
        )
        return result.scalar_one_or_none()

    async def search_by_similarity(
        self,
        embedding: List[float],
        similarity_threshold: float = 0.85,
        limit: int = 5
    ) -> List[tuple[VerifiedSource, float]]:
        """
        Search verified sources by semantic similarity to claim keywords.

        Args:
            embedding: Query embedding vector (1536 dimensions)
            similarity_threshold: Minimum cosine similarity (default 0.85)
            limit: Maximum number of results to return

        Returns:
            List of tuples (VerifiedSource, similarity_score) ordered by similarity desc
        """
        # Using pgvector cosine similarity operator <=>
        # Note: <=> returns distance (0 = identical), so 1 - distance = similarity
        query = select(
            VerifiedSource,
            (1 - VerifiedSource.embedding.cosine_distance(embedding)).label('similarity')
        ).where(
            (1 - VerifiedSource.embedding.cosine_distance(embedding)) >= similarity_threshold
        ).order_by(
            VerifiedSource.embedding.cosine_distance(embedding)
        ).limit(limit)

        result = await self.session.execute(query)
        return [(row[0], row[1]) for row in result.all()]

    async def find_by_title_author(
        self,
        title: str,
        author: str
    ) -> Optional[VerifiedSource]:
        """
        Find verified source by exact title and author match.

        Args:
            title: Source title
            author: Source author

        Returns:
            VerifiedSource or None if not found
        """
        result = await self.session.execute(
            select(VerifiedSource).where(
                VerifiedSource.title == title,
                VerifiedSource.author == author
            )
        )
        return result.scalar_one_or_none()

    async def create(self, verified_source: VerifiedSource) -> VerifiedSource:
        """Create a new verified source."""
        self.session.add(verified_source)
        await self.session.flush()
        await self.session.refresh(verified_source)
        return verified_source

    async def update(self, verified_source: VerifiedSource) -> VerifiedSource:
        """Update an existing verified source."""
        await self.session.flush()
        await self.session.refresh(verified_source)
        return verified_source

    async def delete(self, source_id: UUID) -> bool:
        """Delete a verified source by ID."""
        verified_source = await self.get_by_id(source_id)
        if verified_source:
            await self.session.delete(verified_source)
            await self.session.flush()
            return True
        return False

    async def count(self, source_type: Optional[str] = None) -> int:
        """
        Count verified sources.

        Args:
            source_type: Optional filter by source type (book, paper, ancient_text)

        Returns:
            Total count of matching verified sources
        """
        query = select(func.count()).select_from(VerifiedSource)

        if source_type:
            query = query.where(VerifiedSource.source_type == source_type)

        result = await self.session.execute(query)
        return result.scalar_one()
