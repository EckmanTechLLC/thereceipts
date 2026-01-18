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
from tavily import TavilyClient

from config import settings
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
        self.tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY) if settings.TAVILY_API_KEY else None

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
            response = await self.llm_client.call(
                provider="anthropic",
                model_name="claude-3-5-haiku-20241022",  # Fast, cost-effective
                system_prompt=self.EXTRACTION_PROMPT,
                user_message=user_message,
                temperature=0.7,
                max_tokens=2048
            )

            content = response["content"]

            # Parse JSON response - extract JSON object robustly
            if "```json" in content:
                # Extract from markdown code block
                start = content.index("```json") + 7
                end = content.rindex("```")
                json_str = content[start:end].strip()
            else:
                # Find first '{' and last '}' to extract JSON object
                json_str = content.strip()
                if "{" in json_str and "}" in json_str:
                    start = json_str.index("{")
                    end = json_str.rindex("}") + 1
                    json_str = json_str[start:end]

            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError as e:
                # Log the problematic content for debugging
                print(f"[AUTOSUGGEST] Failed to parse JSON. Content: {content[:500]}")
                raise AutoSuggestServiceError(f"Failed to parse LLM JSON output: {str(e)}")

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

        except AutoSuggestServiceError:
            # Re-raise our own errors
            raise
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

                    # Build source string (where this topic came from)
                    source_name = topic_data.get("source_name", "auto-suggest")
                    if source_name and source_name != "auto-suggest":
                        source = f"auto-suggest: {source_name[:100]}"
                    else:
                        source = "auto-suggest"

                    # Create topic queue entry
                    new_topic = TopicQueue(
                        topic_text=topic_text,
                        priority=priority,
                        status=TopicStatusEnum.QUEUED,
                        source=source
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

    async def discover_topics_from_web(self) -> Dict[str, Any]:
        """
        Automatically discover topics from web sources using Tavily search.

        Searches for recent Christian apologetics content and extracts topics.

        Returns:
            Dict with summary:
                - extracted: Number of topics extracted from search results
                - added: Number of topics added to queue
                - skipped_duplicates: Number skipped due to existing similar claims
                - failed: Number that failed to add
                - sources_searched: Number of web sources searched

        Raises:
            AutoSuggestServiceError: If discovery fails or Tavily not configured
        """
        if not self.tavily_client:
            raise AutoSuggestServiceError(
                "Tavily API key not configured. Set TAVILY_API_KEY environment variable."
            )

        try:
            # Search queries targeting apologetics content
            search_queries = [
                "Christian apologetics recent claims 2026",
                "answers in genesis recent articles",
                "William Lane Craig recent apologetics"
            ]

            all_topics = []
            sources_searched = 0

            for query in search_queries:
                try:
                    print(f"Searching: {query}")
                    # Search with Tavily
                    response = self.tavily_client.search(
                        query=query,
                        max_results=3,
                        search_depth="basic"
                    )

                    if not response or "results" not in response:
                        continue

                    # Extract topics from each search result
                    for result in response["results"]:
                        sources_searched += 1
                        content = result.get("content", "")
                        url = result.get("url", "")
                        title = result.get("title", "")

                        if not content:
                            continue

                        print(f"  → Extracting from: {title[:60]}...")

                        # Extract topics from this source
                        topics = await self.extract_topics_from_text(
                            source_text=content,
                            source_url=url,
                            source_name=title
                        )

                        all_topics.extend(topics)

                except Exception as e:
                    print(f"  → Search failed for '{query}': {str(e)}")
                    continue

            if not all_topics:
                return {
                    "extracted": 0,
                    "added": 0,
                    "skipped_duplicates": 0,
                    "failed": 0,
                    "sources_searched": sources_searched
                }

            # Add discovered topics to queue
            result = await self.add_topics_to_queue(all_topics)

            return {
                "extracted": len(all_topics),
                "added": result["added"],
                "skipped_duplicates": result["skipped_duplicates"],
                "failed": result["failed"],
                "sources_searched": sources_searched
            }

        except Exception as e:
            raise AutoSuggestServiceError(f"Web discovery failed: {str(e)}")


# Global auto-suggest service instance
autosuggest_service = AutoSuggestService()
