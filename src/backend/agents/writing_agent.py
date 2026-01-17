"""
Writing Agent for TheReceipts pipeline.

Fourth agent in the pipeline. Produces:
- Short answer (≤150 words, plain language)
- Deep answer (full detailed analysis)
- Why this claim persists section
- Final prose in calm, direct, forensic tone
"""

import json
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, AgentExecutionError, extract_json_from_response


class WritingAgent(BaseAgent):
    """
    Agent that produces final prose for the claim card.

    Takes all previous analysis and writes:
    - Short answer: Plain-language summary
    - Deep answer: Full detailed analysis
    - Why this claim persists: Psychological/social/institutional reasons
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize WritingAgent."""
        super().__init__(agent_name="writing_agent", db_session=db_session)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce final prose for the claim card.

        Args:
            input_data: Dict containing all previous agent outputs

        Returns:
            Dict containing:
                - short_answer: ≤150 words plain-language summary
                - deep_answer: Full detailed analysis
                - why_persists: List of reasons this claim persists
                - raw_response: Full LLM response

        Raises:
            AgentExecutionError: If execution fails or output cannot be parsed
        """
        claim = input_data.get("claim_text", "")
        verdict = input_data.get("verdict", "")
        evidence_summary = input_data.get("evidence_summary", "")
        confidence_explanation = input_data.get("confidence_explanation", "")

        if not claim:
            raise AgentExecutionError("No claim provided to WritingAgent")

        # Construct user message with all context
        context_summary = json.dumps({
            "claim": claim,
            "claimant": input_data.get("claimant", ""),
            "verdict": verdict,
            "confidence_level": input_data.get("confidence_level", ""),
            "evidence_summary": evidence_summary,
            "confidence_explanation": confidence_explanation,
            "counterevidence": input_data.get("counterevidence", ""),
        }, indent=2)

        user_message = f"""
Write the final prose for this claim analysis:

Context:
{context_summary}

Please respond with a JSON object containing:
{{
  "short_answer": "Plain-language summary in ≤150 words. Must be accessible to non-academics.",
  "deep_answer": "Full detailed analysis with evidence review. 3-5 paragraphs. Calm, direct, forensic tone.",
  "why_persists": [
    "Psychological reason this claim persists",
    "Social reason this claim persists",
    "Institutional reason this claim persists"
  ]
}}

Writing guidelines:
- Calm, direct, forensic tone
- No mocking or rhetorical preaching
- Accessible to non-academics
- No assumption of prior biblical/theological knowledge
- Focus on evidence, not persuasion
"""

        try:
            # Call LLM
            response = await self.call_llm(user_message)
            raw_content = response["content"]

            # Parse JSON using shared utility function
            content = extract_json_from_response(raw_content)
            parsed = json.loads(content)

            # Validate required fields
            required_fields = ["short_answer", "deep_answer", "why_persists"]
            for field in required_fields:
                if field not in parsed:
                    raise AgentExecutionError(
                        f"WritingAgent output missing required field: {field}"
                    )

            # Validate short_answer length (approximately ≤150 words)
            short_answer_words = len(parsed["short_answer"].split())
            if short_answer_words > 175:  # Allow slight buffer
                raise AgentExecutionError(
                    f"WritingAgent short_answer too long: {short_answer_words} words (max 150)"
                )

            return {
                "short_answer": parsed["short_answer"],
                "deep_answer": parsed["deep_answer"],
                "why_persists": parsed["why_persists"],
                "raw_response": raw_content,
                "usage": response.get("usage", {}),
            }

        except json.JSONDecodeError as e:
            raise AgentExecutionError(
                f"WritingAgent failed to parse JSON output: {str(e)}"
            )
        except Exception as e:
            raise AgentExecutionError(
                f"WritingAgent execution failed: {str(e)}"
            )
