"""
Scheduler Service for TheReceipts auto-blog system.

Orchestrates scheduled generation of blog posts:
1. Pick highest priority topic from queue
2. Run DecomposerAgent → component claims (variable 3-12)
3. For each component claim:
   - Semantic search for existing claim card (>0.92 similarity)
   - If found: Reuse existing claim_card_id
   - If not found: Run 5-agent pipeline → new claim card
4. Run BlogComposerAgent → synthesized article
5. Create blog_posts row
6. Queue for admin review
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database.session import AsyncSessionFactory
from database.repositories import (
    TopicQueueRepository,
    ClaimCardRepository,
    BlogPostRepository,
)
from database.models import TopicStatusEnum, TopicQueue, BlogPost, ReviewStatusEnum
from services.pipeline import PipelineOrchestrator
from services.embedding import EmbeddingService, EmbeddingServiceError
from agents.decomposer import DecomposerAgent
from agents.blog_composer import BlogComposerAgent
from agents.base import AgentExecutionError


class SchedulerServiceError(Exception):
    """Raised when scheduler service encounters an error."""
    pass


class SchedulerConfig:
    """Configuration for scheduler behavior."""

    def __init__(
        self,
        enabled: bool = False,
        posts_per_day: int = 1,
        cron_hour: int = 2,
        cron_minute: int = 0,
        max_concurrent: int = 1,  # Run one at a time (sequential)
    ):
        self.enabled = enabled
        self.posts_per_day = posts_per_day
        self.cron_hour = cron_hour
        self.cron_minute = cron_minute
        self.max_concurrent = max_concurrent


class SchedulerService:
    """
    Service for scheduled blog post generation.

    Uses APScheduler to run at configured times, picks highest priority
    topics from queue, and orchestrates full generation flow.
    """

    # Semantic search threshold for deduplication (matches ADR 002/003)
    SEMANTIC_SIMILARITY_THRESHOLD = 0.92

    def __init__(self):
        """Initialize scheduler service."""
        self.scheduler = AsyncIOScheduler()
        self.config = SchedulerConfig()
        self.embedding_service = EmbeddingService()
        self._generation_lock = asyncio.Lock()  # Prevent concurrent generations

    def configure(self, config: SchedulerConfig):
        """
        Update scheduler configuration.

        Args:
            config: New SchedulerConfig
        """
        self.config = config
        self._update_schedule()

    def _update_schedule(self):
        """Update APScheduler job based on current configuration."""
        # Remove existing job if present
        if self.scheduler.get_job("blog_generation"):
            self.scheduler.remove_job("blog_generation")

        if self.config.enabled:
            # Add cron job
            trigger = CronTrigger(
                hour=self.config.cron_hour,
                minute=self.config.cron_minute
            )
            self.scheduler.add_job(
                self._run_scheduled_generation,
                trigger=trigger,
                id="blog_generation",
                name="Blog Post Generation",
                max_instances=1,  # Prevent overlapping runs
            )

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _run_scheduled_generation(self):
        """
        Run scheduled blog post generation.

        Picks highest priority topics and generates blog posts.
        Called automatically by APScheduler at configured time.
        """
        async with self._generation_lock:
            try:
                # Process configured number of posts
                for _ in range(self.config.posts_per_day):
                    await self.generate_next_blog_post()
            except Exception as e:
                print(f"Scheduled generation error: {str(e)}")

    async def generate_next_blog_post(self) -> Optional[Dict[str, Any]]:
        """
        Generate a single blog post from the highest priority queued topic.

        Full flow:
        1. Pick highest priority topic from queue
        2. Run DecomposerAgent → component claims (3-12)
        3. For each component claim:
           - Semantic search for existing claim card (>0.92 similarity)
           - If found: Reuse existing claim_card_id
           - If not found: Run 5-agent pipeline → new claim card
        4. Run BlogComposerAgent → synthesized article
        5. Create blog_posts row
        6. Queue for admin review

        Returns:
            Dict with generation result or None if no topics queued

        Raises:
            SchedulerServiceError: If generation fails
        """
        async with AsyncSessionFactory() as db_session:
            topic_repo = TopicQueueRepository(db_session)

            # Get highest priority queued topic
            topic = await topic_repo.get_next_queued()
            if not topic:
                print("No queued topics available for generation")
                return None

            # Mark topic as processing
            topic.status = TopicStatusEnum.PROCESSING
            await topic_repo.update(topic)
            await db_session.commit()

            try:
                # Step 1: Run DecomposerAgent
                print(f"Decomposing topic: {topic.topic_text}")
                decomposer = DecomposerAgent(db_session)
                decomposer_result = await decomposer.run({
                    "topic": topic.topic_text,
                    "context": ""
                })

                if not decomposer_result["success"]:
                    raise SchedulerServiceError(f"Decomposer failed: {decomposer_result['error']}")

                decomposer_output = decomposer_result["output"]
                component_claims = decomposer_output["component_claims"]
                print(f"Decomposer identified {len(component_claims)} component claims")

                # Step 2: Process each component claim (dedup or generate)
                claim_card_ids: List[UUID] = []
                claim_cards_data: List[Dict[str, Any]] = []

                for i, claim_text in enumerate(component_claims, 1):
                    print(f"Processing claim {i}/{len(component_claims)}: {claim_text[:80]}...")

                    # Check for existing claim card via semantic search
                    # Exclude current blog's claim IDs to prevent intra-blog deduplication
                    existing_card = await self._find_existing_claim(
                        claim_text, db_session, exclude_claim_ids=claim_card_ids
                    )

                    if existing_card:
                        # Reuse existing claim card (avoid duplicates)
                        if existing_card.id not in claim_card_ids:
                            print(f"  → Reusing existing claim card {existing_card.id}")
                            claim_card_ids.append(existing_card.id)
                            claim_cards_data.append(self._claim_card_to_dict(existing_card))
                        else:
                            print(f"  → Skipping duplicate claim card {existing_card.id}")
                    else:
                        # Generate new claim card via 5-agent pipeline
                        print(f"  → Generating new claim card via pipeline")
                        new_card = await self._generate_claim_card(
                            claim_text, db_session
                        )
                        if new_card.id not in claim_card_ids:
                            claim_card_ids.append(new_card.id)
                            claim_cards_data.append(self._claim_card_to_dict(new_card))
                        else:
                            print(f"  → Skipping duplicate claim card {new_card.id}")

                print(f"Claim cards ready: {len(claim_card_ids)} total")

                # Step 3: Run BlogComposerAgent
                print("Composing blog article...")
                composer = BlogComposerAgent(db_session)
                composer_result = await composer.run({
                    "topic": topic.topic_text,
                    "claim_cards": claim_cards_data
                })

                if not composer_result["success"]:
                    raise SchedulerServiceError(f"Composer failed: {composer_result['error']}")

                composer_output = composer_result["output"]
                title = composer_output["title"]
                article_body = composer_output["article_body"]
                word_count = composer_output["word_count"]
                print(f"Article composed: {word_count} words")

                # Step 4: Create BlogPost
                blog_repo = BlogPostRepository(db_session)
                blog_post = BlogPost(
                    topic_queue_id=topic.id,
                    title=title,
                    article_body=article_body,
                    claim_card_ids=claim_card_ids,
                    published_at=None,  # Not published until admin review
                )
                blog_post = await blog_repo.create(blog_post)
                await db_session.commit()

                # Step 5: Update topic status
                topic.status = TopicStatusEnum.COMPLETED
                topic.review_status = ReviewStatusEnum.PENDING_REVIEW
                topic.blog_post_id = blog_post.id
                await topic_repo.update(topic)
                await db_session.commit()

                print(f"Blog post {blog_post.id} created, queued for review")

                return {
                    "success": True,
                    "topic_id": str(topic.id),
                    "blog_post_id": str(blog_post.id),
                    "title": title,
                    "word_count": word_count,
                    "claim_cards_count": len(claim_card_ids),
                }

            except Exception as e:
                # Fail fast - mark topic as failed
                topic.status = TopicStatusEnum.FAILED
                topic.error_message = str(e)
                await topic_repo.update(topic)
                await db_session.commit()

                print(f"Blog post generation failed for topic {topic.id}: {str(e)}")
                raise SchedulerServiceError(
                    f"Blog post generation failed: {str(e)}"
                )

    async def _find_existing_claim(
        self,
        claim_text: str,
        db_session: AsyncSession,
        exclude_claim_ids: Optional[List[UUID]] = None
    ) -> Optional[Any]:
        """
        Search for existing claim card via semantic search.

        Args:
            claim_text: Component claim text to search for
            db_session: Database session
            exclude_claim_ids: Optional list of claim IDs to exclude from search
                               (prevents intra-blog deduplication)

        Returns:
            ClaimCard if found with similarity >= 0.92, else None
        """
        try:
            # Generate embedding for claim text
            embedding = await self.embedding_service.generate_embedding(claim_text)

            # Semantic search (excluding current blog's claims)
            claim_repo = ClaimCardRepository(db_session)
            results = await claim_repo.search_by_embedding(
                embedding=embedding,
                threshold=self.SEMANTIC_SIMILARITY_THRESHOLD,
                limit=1,
                exclude_claim_ids=exclude_claim_ids
            )

            if results:
                claim_card, similarity = results[0]
                print(f"  → Found similar claim (similarity: {similarity:.3f})")
                return claim_card

            return None

        except EmbeddingServiceError as e:
            print(f"  → Embedding generation failed: {str(e)}, treating as novel claim")
            return None

    async def _generate_claim_card(
        self,
        claim_text: str,
        db_session: AsyncSession
    ) -> Any:
        """
        Generate new claim card via 5-agent pipeline.

        Args:
            claim_text: Component claim text to fact-check
            db_session: Database session

        Returns:
            Created ClaimCard

        Raises:
            SchedulerServiceError: If pipeline fails
        """
        try:
            # Run 5-agent pipeline
            pipeline = PipelineOrchestrator(db_session)
            pipeline_result = await pipeline.run_pipeline(
                question=claim_text,
                websocket_session_id=None,  # No websocket for scheduled generation
                connection_manager=None
            )

            if not pipeline_result["success"]:
                raise SchedulerServiceError(
                    f"Pipeline failed: {pipeline_result.get('error', 'Unknown error')}"
                )

            # Create claim card from pipeline output
            claim_repo = ClaimCardRepository(db_session)
            claim_card = await claim_repo.create_from_pipeline_output(
                pipeline_data=pipeline_result["claim_card_data"],
                question=claim_text
            )

            # Generate and store embedding
            embedding = await self.embedding_service.generate_embedding(claim_text)
            await claim_repo.upsert_embedding(claim_card.id, embedding)

            await db_session.commit()

            print(f"  → Created claim card {claim_card.id}")
            return claim_card

        except Exception as e:
            raise SchedulerServiceError(
                f"Claim card generation failed: {str(e)}"
            )

    def _claim_card_to_dict(self, claim_card: Any) -> Dict[str, Any]:
        """
        Convert ClaimCard model to dictionary for BlogComposerAgent.

        Args:
            claim_card: ClaimCard model instance

        Returns:
            Dict with claim card fields
        """
        # Extract sources
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


# Global scheduler service instance
scheduler_service = SchedulerService()
