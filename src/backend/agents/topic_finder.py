"""
Topic Finder Agent for TheReceipts pipeline.

First agent in the pipeline. Identifies:
- The specific claim being made
- Who made the claim (claimant)
- Why this claim matters (context)
"""

import json
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, AgentExecutionError, extract_json_from_response


class TopicFinderAgent(BaseAgent):
    """
    Agent that identifies and structures the claim from user input.

    Takes a question or claim text and extracts:
    - claim: The specific factual assertion being made
    - claimant: Author/organization who made the claim
    - context: Why this claim matters (psychological/social/institutional)
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize TopicFinderAgent."""
        super().__init__(agent_name="topic_finder", db_session=db_session)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify claim, claimant, and context from user question.

        Args:
            input_data: Dict containing:
                - question: User's question or claim text

        Returns:
            Dict containing:
                - claim: The specific claim identified
                - claimant: Who made the claim
                - claim_type: Type of claim (history, science, doctrine, etc.)
                - context: Why this claim matters
                - raw_response: Full LLM response

        Raises:
            AgentExecutionError: If execution fails or output cannot be parsed
        """
        question = input_data.get("question", "")
        if not question:
            raise AgentExecutionError("No question provided to TopicFinderAgent")

        # Construct user message
        user_message = f"""
Question: {question}

Identify the claim, claimant, type, why it matters, and relevant categories.
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
            required_fields = ["claim_text", "claimant", "claim_type", "why_matters"]
            for field in required_fields:
                if field not in parsed:
                    raise AgentExecutionError(
                        f"TopicFinderAgent output missing required field: {field}"
                    )

            return {
                "claim_text": parsed["claim_text"],
                "claimant": parsed["claimant"],
                "claim_type": parsed["claim_type"],
                "why_matters": parsed["why_matters"],
                "category_tags": parsed.get("category_tags", []),
                "raw_response": raw_content,
                "usage": response.get("usage", {}),
            }

        except json.JSONDecodeError as e:
            raise AgentExecutionError(
                f"TopicFinderAgent failed to parse JSON output: {str(e)}"
            )
        except Exception as e:
            raise AgentExecutionError(
                f"TopicFinderAgent execution failed: {str(e)}"
            )
