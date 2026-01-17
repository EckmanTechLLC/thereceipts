"""
Review Service for TheReceipts auto-blog system.

Handles admin review workflow for generated blog posts:
- Approve & Publish: Sets published_at, makes visible in Read page
- Request Revision: Selective re-run (decomposer/pipeline/composer)
- Reject: Mark as rejected, blog post not published
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories import (
    TopicQueueRepository,
    BlogPostRepository,
    ClaimCardRepository,
)
from database.models import ReviewStatusEnum, TopicStatusEnum, BlogPost
from services.pipeline import PipelineOrchestrator
from services.embedding import EmbeddingService, EmbeddingServiceError
from agents.decomposer import DecomposerAgent
from agents.blog_composer import BlogComposerAgent


class ReviewServiceError(Exception):
    """Raised when review service encounters an error."""
    pass


class ReviewService:
    """
    Service for blog post review workflow.

    Provides three actions:
    1. Approve - Publish blog post (sets published_at)
    2. Request Revision - Selective re-run of components
    3. Reject - Mark as rejected (not published)
    """

    # Semantic search threshold (matches ADR 002/003)
    SEMANTIC_SIMILARITY_THRESHOLD = 0.92

    def __init__(self, db_session: AsyncSession):
        """Initialize review service with database session."""
        self.db_session = db_session
        self.topic_repo = TopicQueueRepository(db_session)
        self.blog_repo = BlogPostRepository(db_session)
        self.claim_repo = ClaimCardRepository(db_session)
        self.embedding_service = EmbeddingService()

    async def get_pending_reviews(
        self,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get blog posts pending review.

        Returns topics with review_status='pending_review' along with
        their associated blog posts and claim cards.

        Args:
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            Dict with pending reviews and metadata
        """
        # Get topics pending review (ordered by priority)
        topics = await self.topic_repo.get_all(skip=skip, limit=limit)

        # Filter to only pending_review status
        pending_topics = [
            t for t in topics
            if t.review_status == ReviewStatusEnum.PENDING_REVIEW.value
        ]

        # Build response with blog post details
        reviews = []
        for topic in pending_topics:
            if not topic.blog_post_id:
                continue

            blog_post = await self.blog_repo.get_by_id(topic.blog_post_id)
            if not blog_post:
                continue

            # Get claim card details (deduplicate IDs)
            claim_cards = []
            seen_ids = set()
            for claim_id in blog_post.claim_card_ids:
                if claim_id in seen_ids:
                    continue
                seen_ids.add(claim_id)

                claim = await self.claim_repo.get_by_id(claim_id)
                if claim:
                    claim_cards.append({
                        "id": str(claim.id),
                        "claim_text": claim.claim_text,
                        "claimant": claim.claimant,
                        "verdict": claim.verdict.value,
                        "short_answer": claim.short_answer,
                        "deep_answer": claim.deep_answer,
                        "confidence_level": claim.confidence_level.value,
                        "sources": [
                            {
                                "id": str(s.id),
                                "source_type": s.source_type.value,
                                "citation": s.citation,
                                "url": s.url,
                            }
                            for s in claim.sources
                        ],
                    })

            reviews.append({
                "topic": {
                    "id": str(topic.id),
                    "topic_text": topic.topic_text,
                    "priority": topic.priority,
                    "status": topic.status.value,
                    "source": topic.source,
                    "review_status": topic.review_status,
                    "created_at": topic.created_at.isoformat(),
                    "updated_at": topic.updated_at.isoformat(),
                },
                "blog_post": {
                    "id": str(blog_post.id),
                    "title": blog_post.title,
                    "article_body": blog_post.article_body,
                    "claim_card_ids": [str(cid) for cid in blog_post.claim_card_ids],
                    "created_at": blog_post.created_at.isoformat(),
                },
                "claim_cards": claim_cards,
            })

        return {
            "reviews": reviews,
            "total": len(reviews),
        }

    async def approve_blog_post(
        self,
        topic_id: UUID,
        reviewed_by: str,
        review_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve and publish blog post.

        Sets blog_posts.published_at = NOW() and updates review status.
        Blog article becomes visible in Read page.

        Args:
            topic_id: Topic queue ID
            reviewed_by: Admin username who reviewed
            review_notes: Optional admin notes

        Returns:
            Dict with approval result

        Raises:
            ReviewServiceError: If topic not found or invalid state
        """
        # Get topic
        topic = await self.topic_repo.get_by_id(topic_id)
        if not topic:
            raise ReviewServiceError(f"Topic {topic_id} not found")

        if topic.review_status != ReviewStatusEnum.PENDING_REVIEW.value:
            raise ReviewServiceError(
                f"Topic must be pending_review (current: {topic.review_status})"
            )

        # Get blog post
        if not topic.blog_post_id:
            raise ReviewServiceError("Topic has no associated blog post")

        blog_post = await self.blog_repo.get_by_id(topic.blog_post_id)
        if not blog_post:
            raise ReviewServiceError("Blog post not found")

        # Approve and publish
        blog_post.published_at = datetime.utcnow()
        blog_post.reviewed_by = reviewed_by
        blog_post.review_notes = review_notes
        await self.blog_repo.update(blog_post)

        # Update topic review status
        topic.review_status = ReviewStatusEnum.APPROVED.value
        topic.reviewed_at = datetime.utcnow()
        await self.topic_repo.update(topic)

        await self.db_session.commit()

        return {
            "success": True,
            "topic_id": str(topic_id),
            "blog_post_id": str(blog_post.id),
            "published_at": blog_post.published_at.isoformat(),
            "message": "Blog post approved and published"
        }

    async def reject_blog_post(
        self,
        topic_id: UUID,
        reviewed_by: str,
        admin_feedback: str
    ) -> Dict[str, Any]:
        """
        Reject blog post.

        Blog post NOT published (won't appear in Read page).
        Claim cards remain in database (still in Audits, still usable in chat).

        Args:
            topic_id: Topic queue ID
            reviewed_by: Admin username who reviewed
            admin_feedback: Reason for rejection

        Returns:
            Dict with rejection result

        Raises:
            ReviewServiceError: If topic not found or invalid state
        """
        # Get topic
        topic = await self.topic_repo.get_by_id(topic_id)
        if not topic:
            raise ReviewServiceError(f"Topic {topic_id} not found")

        if topic.review_status != ReviewStatusEnum.PENDING_REVIEW.value:
            raise ReviewServiceError(
                f"Topic must be pending_review (current: {topic.review_status})"
            )

        # Get blog post (to record reviewer)
        if topic.blog_post_id:
            blog_post = await self.blog_repo.get_by_id(topic.blog_post_id)
            if blog_post:
                blog_post.reviewed_by = reviewed_by
                blog_post.review_notes = f"REJECTED: {admin_feedback}"
                await self.blog_repo.update(blog_post)

        # Update topic review status
        topic.review_status = ReviewStatusEnum.REJECTED.value
        topic.reviewed_at = datetime.utcnow()
        topic.admin_feedback = admin_feedback
        await self.topic_repo.update(topic)

        await self.db_session.commit()

        return {
            "success": True,
            "topic_id": str(topic_id),
            "message": "Blog post rejected"
        }

    async def request_revision(
        self,
        topic_id: UUID,
        reviewed_by: str,
        admin_feedback: str,
        revision_scope: str,
        revision_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Request revision with selective re-run.

        Admin specifies which component to re-run:
        - "decomposer": Re-decompose topic into component claims
        - "claim_pipeline": Re-run specific claim card(s) through 5-agent pipeline
        - "composer": Re-run blog composer (title + article body)

        Args:
            topic_id: Topic queue ID
            reviewed_by: Admin username who reviewed
            admin_feedback: Admin's revision instructions
            revision_scope: What to re-run (decomposer/claim_pipeline/composer)
            revision_details: Additional details (e.g., which claim_card_ids to re-run)

        Returns:
            Dict with revision result

        Raises:
            ReviewServiceError: If invalid scope or execution fails
        """
        # Get topic
        topic = await self.topic_repo.get_by_id(topic_id)
        if not topic:
            raise ReviewServiceError(f"Topic {topic_id} not found")

        if topic.review_status != ReviewStatusEnum.PENDING_REVIEW.value:
            raise ReviewServiceError(
                f"Topic must be pending_review (current: {topic.review_status})"
            )

        # Get existing blog post
        if not topic.blog_post_id:
            raise ReviewServiceError("Topic has no associated blog post")

        blog_post = await self.blog_repo.get_by_id(topic.blog_post_id)
        if not blog_post:
            raise ReviewServiceError("Blog post not found")

        # Validate revision scope
        valid_scopes = ["decomposer", "claim_pipeline", "composer"]
        if revision_scope not in valid_scopes:
            raise ReviewServiceError(
                f"Invalid revision_scope: {revision_scope}. "
                f"Must be one of: {', '.join(valid_scopes)}"
            )

        # Record feedback and mark as needs_revision
        topic.review_status = ReviewStatusEnum.NEEDS_REVISION.value
        topic.reviewed_at = datetime.utcnow()
        topic.admin_feedback = admin_feedback
        await self.topic_repo.update(topic)

        blog_post.reviewed_by = reviewed_by
        blog_post.review_notes = f"REVISION REQUESTED ({revision_scope}): {admin_feedback}"
        await self.blog_repo.update(blog_post)

        await self.db_session.commit()

        # Execute revision based on scope
        try:
            if revision_scope == "decomposer":
                result = await self._rerun_decomposer(topic, blog_post)
            elif revision_scope == "claim_pipeline":
                result = await self._rerun_claim_pipeline(
                    topic, blog_post, revision_details
                )
            elif revision_scope == "composer":
                result = await self._rerun_composer(topic, blog_post)
            else:
                raise ReviewServiceError(f"Unhandled revision scope: {revision_scope}")

            return {
                "success": True,
                "topic_id": str(topic_id),
                "revision_scope": revision_scope,
                "message": "Revision executed, awaiting re-review",
                "details": result
            }

        except Exception as e:
            # Revision failed, update status
            topic.status = TopicStatusEnum.FAILED
            topic.error_message = f"Revision failed ({revision_scope}): {str(e)}"
            await self.topic_repo.update(topic)
            await self.db_session.commit()

            raise ReviewServiceError(f"Revision execution failed: {str(e)}")

    async def _rerun_decomposer(
        self,
        topic: Any,
        blog_post: BlogPost
    ) -> Dict[str, Any]:
        """
        Re-run decomposer agent.

        Regenerates component claims, then re-runs pipeline + composer.
        """
        print(f"Re-running decomposer for topic: {topic.topic_text}")

        # Run DecomposerAgent
        decomposer = DecomposerAgent(self.db_session)
        decomposer_result = await decomposer.run({
            "topic": topic.topic_text,
            "context": ""
        })

        if not decomposer_result["success"]:
            raise ReviewServiceError(f"Decomposer failed: {decomposer_result['error']}")

        decomposer_output = decomposer_result["output"]
        component_claims = decomposer_output["component_claims"]
        print(f"Decomposer identified {len(component_claims)} component claims")

        # Process each component claim (dedup or generate)
        claim_card_ids: List[UUID] = []
        claim_cards_data: List[Dict[str, Any]] = []

        for claim_text in component_claims:
            # Check for existing claim card
            existing_card = await self._find_existing_claim(claim_text)

            if existing_card:
                if existing_card.id not in claim_card_ids:
                    claim_card_ids.append(existing_card.id)
                    claim_cards_data.append(self._claim_card_to_dict(existing_card))
            else:
                # Generate new claim card
                new_card = await self._generate_claim_card(claim_text)
                if new_card.id not in claim_card_ids:
                    claim_card_ids.append(new_card.id)
                    claim_cards_data.append(self._claim_card_to_dict(new_card))

        # Re-run composer
        composer = BlogComposerAgent(self.db_session)
        composer_result = await composer.run({
            "topic": topic.topic_text,
            "claim_cards": claim_cards_data
        })

        if not composer_result["success"]:
            raise ReviewServiceError(f"Composer failed: {composer_result['error']}")

        composer_output = composer_result["output"]

        # Update blog post
        blog_post.title = composer_output["title"]
        blog_post.article_body = composer_output["article_body"]
        blog_post.claim_card_ids = claim_card_ids
        await self.blog_repo.update(blog_post)

        # Reset review status to pending
        topic.review_status = ReviewStatusEnum.PENDING_REVIEW.value
        await self.topic_repo.update(topic)

        await self.db_session.commit()

        return {
            "component_claims_count": len(component_claims),
            "claim_cards_count": len(claim_card_ids),
            "word_count": composer_output["word_count"]
        }

    async def _rerun_claim_pipeline(
        self,
        topic: Any,
        blog_post: BlogPost,
        revision_details: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Re-run specific claim card(s) through 5-agent pipeline.

        Admin specifies which claim_card_ids to regenerate.
        """
        if not revision_details or "claim_card_ids" not in revision_details:
            raise ReviewServiceError(
                "revision_details must include 'claim_card_ids' array"
            )

        claim_ids_to_regenerate = [
            UUID(cid) for cid in revision_details["claim_card_ids"]
        ]

        print(f"Re-running pipeline for {len(claim_ids_to_regenerate)} claim cards")

        # Get current claim cards
        current_claim_cards = []
        for claim_id in blog_post.claim_card_ids:
            claim = await self.claim_repo.get_by_id(claim_id)
            if claim:
                current_claim_cards.append(claim)

        # Regenerate specified claim cards
        new_claim_card_ids = []
        claim_cards_data = []

        for claim in current_claim_cards:
            if claim.id in claim_ids_to_regenerate:
                # Regenerate this claim card
                print(f"Regenerating claim card: {claim.claim_text[:80]}...")
                new_card = await self._generate_claim_card(claim.claim_text)
                if new_card.id not in new_claim_card_ids:
                    new_claim_card_ids.append(new_card.id)
                    claim_cards_data.append(self._claim_card_to_dict(new_card))
            else:
                # Keep existing claim card
                if claim.id not in new_claim_card_ids:
                    new_claim_card_ids.append(claim.id)
                    claim_cards_data.append(self._claim_card_to_dict(claim))

        # Re-run composer with updated claim cards
        composer = BlogComposerAgent(self.db_session)
        composer_result = await composer.run({
            "topic": topic.topic_text,
            "claim_cards": claim_cards_data
        })

        if not composer_result["success"]:
            raise ReviewServiceError(f"Composer failed: {composer_result['error']}")

        composer_output = composer_result["output"]

        # Update blog post
        blog_post.title = composer_output["title"]
        blog_post.article_body = composer_output["article_body"]
        blog_post.claim_card_ids = new_claim_card_ids
        await self.blog_repo.update(blog_post)

        # Reset review status to pending
        topic.review_status = ReviewStatusEnum.PENDING_REVIEW.value
        await self.topic_repo.update(topic)

        await self.db_session.commit()

        return {
            "regenerated_count": len(claim_ids_to_regenerate),
            "total_claim_cards": len(new_claim_card_ids),
            "word_count": composer_output["word_count"]
        }

    async def _rerun_composer(
        self,
        topic: Any,
        blog_post: BlogPost
    ) -> Dict[str, Any]:
        """
        Re-run blog composer agent.

        Regenerates title + article_body using existing claim cards.
        """
        print(f"Re-running composer for topic: {topic.topic_text}")

        # Get existing claim cards
        claim_cards_data = []
        for claim_id in blog_post.claim_card_ids:
            claim = await self.claim_repo.get_by_id(claim_id)
            if claim:
                claim_cards_data.append(self._claim_card_to_dict(claim))

        # Re-run composer
        composer = BlogComposerAgent(self.db_session)
        composer_result = await composer.run({
            "topic": topic.topic_text,
            "claim_cards": claim_cards_data
        })

        if not composer_result["success"]:
            raise ReviewServiceError(f"Composer failed: {composer_result['error']}")

        composer_output = composer_result["output"]

        # Update blog post
        blog_post.title = composer_output["title"]
        blog_post.article_body = composer_output["article_body"]
        await self.blog_repo.update(blog_post)

        # Reset review status to pending
        topic.review_status = ReviewStatusEnum.PENDING_REVIEW.value
        await self.topic_repo.update(topic)

        await self.db_session.commit()

        return {
            "word_count": composer_output["word_count"],
            "title": composer_output["title"]
        }

    async def _find_existing_claim(
        self,
        claim_text: str
    ) -> Optional[Any]:
        """Search for existing claim card via semantic search."""
        try:
            embedding = await self.embedding_service.generate_embedding(claim_text)
            results = await self.claim_repo.search_by_embedding(
                embedding=embedding,
                threshold=self.SEMANTIC_SIMILARITY_THRESHOLD,
                limit=1
            )

            if results:
                return results[0][0]  # Return claim_card (first element of tuple)
            return None

        except EmbeddingServiceError:
            return None

    async def _generate_claim_card(
        self,
        claim_text: str
    ) -> Any:
        """Generate new claim card via 5-agent pipeline."""
        pipeline = PipelineOrchestrator(self.db_session)
        pipeline_result = await pipeline.run_pipeline(
            question=claim_text,
            websocket_session_id=None,
            connection_manager=None
        )

        if not pipeline_result["success"]:
            raise ReviewServiceError(
                f"Pipeline failed: {pipeline_result.get('error', 'Unknown error')}"
            )

        # Create claim card
        claim_card = await self.claim_repo.create_from_pipeline_output(
            pipeline_data=pipeline_result["claim_card_data"],
            question=claim_text
        )

        # Generate and store embedding
        embedding = await self.embedding_service.generate_embedding(claim_text)
        await self.claim_repo.upsert_embedding(claim_card.id, embedding)

        await self.db_session.commit()

        return claim_card

    def _claim_card_to_dict(self, claim_card: Any) -> Dict[str, Any]:
        """Convert ClaimCard model to dictionary."""
        primary_sources = [
            {
                "citation": s.citation,
                "url": s.url,
                "quote_text": s.quote_text,
            }
            for s in claim_card.sources
            if s.source_type.value == "primary_historical"
        ]

        scholarly_sources = [
            {
                "citation": s.citation,
                "url": s.url,
                "quote_text": s.quote_text,
            }
            for s in claim_card.sources
            if s.source_type.value == "scholarly_peer_reviewed"
        ]

        return {
            "claim_text": claim_card.claim_text,
            "verdict": claim_card.verdict.value,
            "short_answer": claim_card.short_answer,
            "deep_answer": claim_card.deep_answer,
            "confidence_level": claim_card.confidence_level.value,
            "primary_sources": primary_sources,
            "scholarly_sources": scholarly_sources,
        }
