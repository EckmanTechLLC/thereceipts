"""
Blog Composer Agent for TheReceipts auto-blog system.

Runs AFTER the 5-agent pipeline generates component claim cards. Synthesizes
claim card findings into a cohesive narrative prose article for publication.

Example:
    Input: Topic "Noah's Flood" + 5 claim cards with verdicts/evidence
    Output: Title + full synthesized article (500-1500 words)
"""

import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, AgentExecutionError, extract_json_from_response


class BlogComposerAgent(BaseAgent):
    """
    Agent that generates full synthesized prose articles from claim cards.

    Takes a topic and generated claim cards, writes engaging narrative prose
    that synthesizes findings into a cohesive story.

    Output includes:
    - Article title (engaging, accurate, not clickbait)
    - Article body (500-1500 words of synthesized prose)
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize BlogComposerAgent."""
        super().__init__(agent_name="blog_composer", db_session=db_session)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate article title + synthesized prose body from claim cards.

        Args:
            input_data: Dict containing:
                - topic: Topic text (e.g., "Noah's Flood")
                - claim_cards: List of claim card dicts with full content:
                    - claim_text
                    - verdict
                    - short_answer
                    - deep_answer
                    - sources (primary + scholarly)
                    - confidence_level
                    - etc.

        Returns:
            Dict containing:
                - title: Article title (engaging, accurate)
                - article_body: Full synthesized prose article (500-1500 words)
                - word_count: Word count of article body
                - references: Structured references to claim cards
                - raw_response: Full LLM response
                - usage: Token usage stats

        Raises:
            AgentExecutionError: If execution fails or output cannot be parsed
        """
        topic = input_data.get("topic", "")
        claim_cards = input_data.get("claim_cards", [])

        if not topic:
            raise AgentExecutionError("No topic provided to BlogComposerAgent")

        if not claim_cards or len(claim_cards) == 0:
            raise AgentExecutionError(
                "No claim cards provided to BlogComposerAgent. "
                "At least one claim card required to compose article."
            )

        # Format claim cards for LLM
        formatted_cards = self._format_claim_cards(claim_cards)

        # Construct user message
        user_message = f"""
Topic: {topic}

Component Claim Cards:
{formatted_cards}

Generate a synthesized article (title + prose body) that tells a cohesive story about what the evidence reveals.
Output JSON only, no other text.
"""

        try:
            # Call LLM
            response = await self.call_llm(user_message)
            raw_content = response["content"]

            # Parse JSON using shared utility function
            content = extract_json_from_response(raw_content)
            parsed = json.loads(content)

            # Validate required fields (match system prompt format)
            required_fields = ["title", "article_body"]
            for field in required_fields:
                if field not in parsed:
                    raise AgentExecutionError(
                        f"BlogComposerAgent output missing required field: {field}"
                    )

            article_body = parsed["article_body"]
            word_count = len(article_body.split())

            # Validate article length (500-1500 words as specified in ADR 003)
            if word_count < 400:  # Allow slight flexibility (400-1600)
                raise AgentExecutionError(
                    f"BlogComposerAgent article too short: {word_count} words "
                    "(expected 500-1500 words)"
                )
            if word_count > 1600:
                raise AgentExecutionError(
                    f"BlogComposerAgent article too long: {word_count} words "
                    "(expected 500-1500 words)"
                )

            return {
                "topic": topic,
                "title": parsed["title"],
                "article_body": article_body,
                "word_count": word_count,
                "references": parsed.get("references", []),
                "raw_response": raw_content,
                "usage": response.get("usage", {}),
            }

        except json.JSONDecodeError as e:
            raise AgentExecutionError(
                f"BlogComposerAgent failed to parse JSON output: {str(e)}"
            )
        except Exception as e:
            raise AgentExecutionError(
                f"BlogComposerAgent execution failed: {str(e)}"
            )

    def _format_claim_cards(self, claim_cards: List[Dict[str, Any]]) -> str:
        """
        Format claim cards for LLM consumption.

        Args:
            claim_cards: List of claim card dicts

        Returns:
            Formatted string with claim card summaries
        """
        formatted = []
        for i, card in enumerate(claim_cards, 1):
            claim_text = card.get("claim_text", "Unknown claim")
            verdict = card.get("verdict", "Unknown")
            short_answer = card.get("short_answer", "")
            deep_answer = card.get("deep_answer", "")
            confidence = card.get("confidence_level", "Unknown")

            # Extract key sources
            primary_sources = card.get("primary_sources", [])
            scholarly_sources = card.get("scholarly_sources", [])
            source_count = len(primary_sources) + len(scholarly_sources)

            formatted.append(f"""
Claim Card {i}:
  Claim: {claim_text}
  Verdict: {verdict}
  Confidence: {confidence}
  Short Answer: {short_answer}
  Deep Answer: {deep_answer[:500]}{'...' if len(deep_answer) > 500 else ''}
  Sources: {source_count} total ({len(primary_sources)} primary, {len(scholarly_sources)} scholarly)
""")

        return "\n".join(formatted)
