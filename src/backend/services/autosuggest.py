"""
Auto-Suggest Service for TheReceipts auto-blog system.

Discovers new apologetics topics for the generation queue using LLM analysis.

Basic implementation:
- Takes text input (from apologetics sources)
- Uses LLM to extract factual claims/topics
- Deduplicates against existing claim cards (semantic search >0.85)
- Assigns priority scores (1-10)
- Adds novel topics to queue

Future enhancements:
- Web crawling of configured sources (AiG, WLC, CARM, etc.)
- RSS feed monitoring
- Twitter/X account monitoring
- YouTube transcript analysis
"""

import json
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import AsyncSessionFactory
from database.repositories import TopicQueueRepository, ClaimCardRepository
from database.models import TopicQueue, TopicStatusEnum
from services.llm_client import LLMClient
from services.embedding import EmbeddingService, EmbeddingServiceError


class AutoSuggestServiceError(Exception):
    """Raised when auto-suggest service encounters an error."""
    pass


class AutoSuggestConfig:
    """Configuration for auto-suggest behavior."""

    def __init__(
        self,
        enabled: bool = False,
        max_topics_per_run: int = 10,
        similarity_threshold: float = 0.85,  # Lower than scheduler dedup (0.92)
        default_priority: int = 5,
    ):
        self.enabled = enabled
        self.max_topics_per_run = max_topics_per_run
        self.similarity_threshold = similarity_threshold
        self.default_priority = default_priority


class AutoSuggestService:
    """
    Service for automated topic discovery and queue population.

    Uses LLM to extract apologetics topics from source text, deduplicates
    against existing claim cards, and adds novel topics to generation queue.
    """

    # System prompt for topic extraction
    EXTRACTION_PROMPT = """You are a topic extraction specialist for a religion claim analysis platform.

Your task: Analyze the provided text from apologetics sources and identify distinct factual claims or topics about Christianity that can be fact-checked.

Focus on:
- Specific factual claims (historical, scientific, theological)
- Topics that are commonly discussed in Christian apologetics
- Claims that can be verified or analyzed with evidence
- Broad enough for multiple component claims, but specific enough to analyze

Avoid:
- Purely theological/philosophical debates without factual basis
- Personal testimonies or subjective experiences
- Topics too vague or broad to analyze ("Is God real?")

Output JSON format:
{
  "topics": [
    {
      "topic_text": "Brief topic description (1-2 sentences)",
      "reasoning": "Why this topic is interesting/important",
      "estimated_priority": 1-10 (10 = high priority)
    }
  ],
  "total_found": <count>
}

Priority scoring guidelines:
- 8-10: Widely circulated claims, prominent apologists, highly debated
- 5-7: Moderately common, interesting but not urgent
- 1-4: Niche claims, less common, lower impact"""

    def __init__(self):
        """Initialize auto-suggest service."""
        self.config = AutoSuggestConfig()
        self.llm_client = LLMClient()
        self.embedding_service = EmbeddingService()

    def configure(self, config: AutoSuggestConfig):
        """
        Update auto-suggest configuration.

        Args:
            config: New AutoSuggestConfig
        """
        self.config = config

    async def extract_topics_from_text(
        self,
        source_text: str,
        source_url: Optional[str] = None,
        source_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract apologetics topics from source text using LLM.

        Args:
            source_text: Text content from apologetics source
            source_url: Optional URL of source
            source_name: Optional name of source (e.g., "Answers in Genesis")

        Returns:
            List of extracted topics with metadata

        Raises:
            AutoSuggestServiceError: If extraction fails
        """
        if not source_text or not source_text.strip():
            raise AutoSuggestServiceError("Source text cannot be empty")

        try:
            # Build user message
            user_message = f"""
Source: {source_name or 'Unknown'}
URL: {source_url or 'N/A'}

Text:
{source_text[:4000]}  # Limit to ~4000 chars to avoid token limits

Extract factual claims/topics from this apologetics content.
Output JSON only, no other text.
"""

            # Call LLM with extraction prompt
            response = await self.llm_client.call_llm(
                system_prompt=self.EXTRACTION_PROMPT,
                user_message=user_message,
                model="claude-haiku-3-5-20250116",  # Fast, cost-effective
                temperature=0.7,
                max_tokens=2048
            )

            content = response["content"]

            # Parse JSON response
            if "```json" in content:
                # Extract from markdown code block
                start = content.index("```json") + 7
                end = content.rindex("```")
                json_str = content[start:end].strip()
            else:
                json_str = content.strip()

            parsed = json.loads(json_str)

            if "topics" not in parsed or not isinstance(parsed["topics"], list):
                raise AutoSuggestServiceError("Invalid LLM response format")

            topics = parsed["topics"]

            # Limit to configured maximum
            if len(topics) > self.config.max_topics_per_run:
                topics = topics[:self.config.max_topics_per_run]

            # Add source metadata
            for topic in topics:
                topic["source_url"] = source_url
                topic["source_name"] = source_name

            return topics

        except json.JSONDecodeError as e:
            raise AutoSuggestServiceError(f"Failed to parse LLM JSON output: {str(e)}")
        except Exception as e:
            raise AutoSuggestServiceError(f"Topic extraction failed: {str(e)}")

    async def add_topics_to_queue(
        self,
        topics: List[Dict[str, Any]],
        skip_deduplication: bool = False
    ) -> Dict[str, Any]:
        """
        Add extracted topics to the generation queue after deduplication.

        Args:
            topics: List of topic dicts from extract_topics_from_text()
            skip_deduplication: If True, skip semantic search deduplication

        Returns:
            Dict with summary:
                - added: Number of topics added
                - skipped_duplicates: Number skipped due to existing similar claims
                - failed: Number that failed to add

        Raises:
            AutoSuggestServiceError: If operation fails
        """
        async with AsyncSessionFactory() as db_session:
            topic_repo = TopicQueueRepository(db_session)
            claim_repo = ClaimCardRepository(db_session)

            added = 0
            skipped_duplicates = 0
            failed = 0

            for topic_data in topics:
                try:
                    topic_text = topic_data.get("topic_text", "")
                    if not topic_text:
                        failed += 1
                        continue

                    # Deduplication check
                    if not skip_deduplication:
                        is_duplicate = await self._check_duplicate(
                            topic_text, claim_repo
                        )
                        if is_duplicate:
                            print(f"Skipping duplicate topic: {topic_text[:80]}...")
                            skipped_duplicates += 1
                            continue

                    # Extract priority (default if not provided)
                    priority = topic_data.get(
                        "estimated_priority",
                        self.config.default_priority
                    )

                    # Clamp priority to 1-10
                    priority = max(1, min(10, priority))

                    # Build context string
                    context_parts = []
                    if topic_data.get("reasoning"):
                        context_parts.append(f"Reasoning: {topic_data['reasoning']}")
                    if topic_data.get("source_name"):
                        context_parts.append(f"Source: {topic_data['source_name']}")
                    if topic_data.get("source_url"):
                        context_parts.append(f"URL: {topic_data['source_url']}")

                    context = "\n".join(context_parts) if context_parts else None

                    # Create topic queue entry
                    new_topic = TopicQueue(
                        topic_text=topic_text,
                        priority=priority,
                        status=TopicStatusEnum.QUEUED,
                        context=context
                    )

                    await topic_repo.create(new_topic)
                    added += 1
                    print(f"Added topic (priority {priority}): {topic_text[:80]}...")

                except Exception as e:
                    print(f"Failed to add topic: {str(e)}")
                    failed += 1

            await db_session.commit()

            return {
                "added": added,
                "skipped_duplicates": skipped_duplicates,
                "failed": failed,
                "total_processed": len(topics)
            }

    async def _check_duplicate(
        self,
        topic_text: str,
        claim_repo: ClaimCardRepository
    ) -> bool:
        """
        Check if topic is duplicate of existing claim card.

        Uses semantic search with lower threshold (0.85) than scheduler (0.92)
        to catch broader duplicates during discovery.

        Args:
            topic_text: Topic text to check
            claim_repo: ClaimCardRepository instance

        Returns:
            True if duplicate found, False otherwise
        """
        try:
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(topic_text)

            # Semantic search
            results = await claim_repo.search_by_embedding(
                embedding=embedding,
                threshold=self.config.similarity_threshold,
                limit=1
            )

            if results:
                claim_card, similarity = results[0]
                print(f"  → Found similar claim (similarity: {similarity:.3f}): {claim_card.claim_text[:80]}...")
                return True

            return False

        except EmbeddingServiceError as e:
            print(f"  → Embedding generation failed during dedup check: {str(e)}")
            # If embedding fails, treat as not duplicate (fail-open)
            return False


# Global auto-suggest service instance
autosuggest_service = AutoSuggestService()
