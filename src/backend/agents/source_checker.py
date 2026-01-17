"""
Source Checker Agent for TheReceipts pipeline.

Second agent in the pipeline. Collects:
- Primary historical sources (ancient texts, manuscripts, councils)
- Scholarly peer-reviewed sources (academic consensus)
"""

import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, AgentExecutionError, extract_json_from_response


class SourceCheckerAgent(BaseAgent):
    """
    Agent that researches and validates sources for the claim.

    Takes claim identification from TopicFinderAgent and collects:
    - Primary historical sources
    - Scholarly peer-reviewed sources
    - Relevant quotes and citations
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize SourceCheckerAgent."""
        super().__init__(agent_name="source_checker", db_session=db_session)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Research and collect sources for the claim.

        Args:
            input_data: Dict containing:
                - claim: The claim to research
                - claimant: Who made the claim
                - claim_type: Type of claim
                - context: Why it matters

        Returns:
            Dict containing:
                - primary_sources: List of primary historical sources
                - scholarly_sources: List of scholarly peer-reviewed sources
                - evidence_summary: Brief summary of what sources show
                - raw_response: Full LLM response

        Raises:
            AgentExecutionError: If execution fails or output cannot be parsed
        """
        claim = input_data.get("claim_text", "")
        claimant = input_data.get("claimant", "")
        claim_type = input_data.get("claim_type", "")

        if not claim:
            raise AgentExecutionError("No claim provided to SourceCheckerAgent")

        # Construct user message
        user_message = f"""
Research sources for this claim:

Claim: {claim}
Claimant: {claimant}
Claim Type: {claim_type}

Please respond with a valid JSON object containing:
{{
  "primary_sources": [
    {{
      "citation": "Full citation",
      "quote": "Concise excerpt (typically 2-4 sentences) - key passage only",
      "url": "URL if verifiable, empty string if not",
      "usage_context": "How this source is used (e.g., 'Establishes dating', 'Shows original text')"
    }}
  ],
  "scholarly_sources": [
    {{
      "citation": "Full citation with page numbers",
      "quote": "Concise excerpt (typically 2-4 sentences) showing what source says",
      "url": "URL if verifiable, empty string if not",
      "usage_context": "How this source supports analysis (e.g., 'Demonstrates consensus', 'Refutes claim X')"
    }}
  ],
  "evidence_summary": "Brief summary of what the evidence shows (2-3 sentences)"
}}

CRITICAL CONSTRAINTS:
- Keep quotes concise (typically 2-4 sentences) - excerpt key passages only
- Use empty string ("") for url if you cannot verify it matches the citation
- Properly escape all quotes and special characters in JSON strings (use \\" for quotes inside strings)
- Include usage_context explaining how each source is used
- Primary sources: Original texts, manuscripts, historical documents
- Scholarly sources: Peer-reviewed academic work, not apologetics
"""

        try:
            # Call LLM
            response = await self.call_llm(user_message)
            raw_content = response["content"]

            # Parse JSON using shared utility function
            content = extract_json_from_response(raw_content)
            parsed = json.loads(content)

            # Validate required fields
            required_fields = ["primary_sources", "scholarly_sources", "evidence_summary"]
            for field in required_fields:
                if field not in parsed:
                    raise AgentExecutionError(
                        f"SourceCheckerAgent output missing required field: {field}"
                    )

            return {
                "primary_sources": parsed["primary_sources"],
                "scholarly_sources": parsed["scholarly_sources"],
                "evidence_summary": parsed["evidence_summary"],
                "raw_response": raw_content,
                "usage": response.get("usage", {}),
            }

        except json.JSONDecodeError as e:
            # Include first 500 chars of raw output for debugging
            preview = raw_content[:500] if len(raw_content) > 500 else raw_content
            raise AgentExecutionError(
                f"SourceCheckerAgent failed to parse JSON output: {str(e)}\n\nRaw output preview:\n{preview}"
            )
        except Exception as e:
            raise AgentExecutionError(
                f"SourceCheckerAgent execution failed: {str(e)}"
            )
