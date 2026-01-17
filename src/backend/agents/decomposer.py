"""
Decomposer Agent for TheReceipts auto-blog system.

Runs BEFORE the 5-agent pipeline. Breaks topics into component factual claims
for comprehensive analysis.

Example:
    Topic: "Noah's Flood"
    Output: 3-12 component claims (variable count based on topic complexity)
        - "A global flood covered the entire Earth ~4,000 years ago"
        - "Noah's Ark could fit all animal species"
        - "Geological evidence supports a worldwide flood"
        - etc.
"""

import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, AgentExecutionError, extract_json_from_response


class DecomposerAgent(BaseAgent):
    """
    Agent that breaks topics into component factual claims.

    Takes a broad topic and identifies distinct factual claims that can be
    independently fact-checked through the 5-agent pipeline.

    Number of claims is variable (3-12) based on topic complexity.
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize DecomposerAgent."""
        super().__init__(agent_name="decomposer", db_session=db_session)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Break topic into component factual claims.

        Args:
            input_data: Dict containing:
                - topic: Topic text to decompose (e.g., "Noah's Flood")
                - context: Optional context from topic queue (priority, source, etc.)

        Returns:
            Dict containing:
                - component_claims: List of claim texts (variable count: 3-12)
                - topic: Original topic text
                - claim_count: Number of component claims identified
                - reasoning: LLM's reasoning for the decomposition
                - raw_response: Full LLM response
                - usage: Token usage stats

        Raises:
            AgentExecutionError: If execution fails or output cannot be parsed
        """
        topic = input_data.get("topic", "")
        if not topic:
            raise AgentExecutionError("No topic provided to DecomposerAgent")

        context = input_data.get("context", "")

        # Construct user message
        user_message = f"""
Topic: {topic}

{f"Context: {context}" if context else ""}

Identify distinct factual claims within this topic that can be independently fact-checked.
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
            if "component_claims" not in parsed:
                raise AgentExecutionError(
                    "DecomposerAgent output missing required field: component_claims"
                )

            component_claims = parsed["component_claims"]
            if not isinstance(component_claims, list):
                raise AgentExecutionError(
                    "DecomposerAgent component_claims must be a list"
                )

            if len(component_claims) < 3 or len(component_claims) > 12:
                raise AgentExecutionError(
                    f"DecomposerAgent produced {len(component_claims)} claims "
                    "(expected 3-12 based on topic complexity)"
                )

            return {
                "topic": topic,
                "component_claims": component_claims,
                "claim_count": len(component_claims),
                "reasoning": parsed.get("reasoning", ""),
                "raw_response": raw_content,
                "usage": response.get("usage", {}),
            }

        except json.JSONDecodeError as e:
            raise AgentExecutionError(
                f"DecomposerAgent failed to parse JSON output: {str(e)}"
            )
        except Exception as e:
            raise AgentExecutionError(
                f"DecomposerAgent execution failed: {str(e)}"
            )
