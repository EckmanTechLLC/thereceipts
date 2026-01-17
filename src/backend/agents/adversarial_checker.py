"""
Adversarial Checker Agent for TheReceipts pipeline.

Third agent in the pipeline. Attempts to:
- Falsify the draft verdict
- Verify quotes are not out of context
- Check that sources actually support claims
- Ensure confidence is not overstated
"""

import json
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, AgentExecutionError, extract_json_from_response


class AdversarialCheckerAgent(BaseAgent):
    """
    Agent that attempts to falsify the analysis and verify source accuracy.

    Takes claim and sources from previous agents and:
    - Attempts to find counterevidence
    - Verifies quotes are in context
    - Checks for apologetics techniques
    - Assesses confidence level
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize AdversarialCheckerAgent."""
        super().__init__(agent_name="adversarial_checker", db_session=db_session)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to falsify the analysis and verify sources.

        Args:
            input_data: Dict containing all previous agent outputs

        Returns:
            Dict containing:
                - verdict: Verdict category (True/Misleading/False/Unfalsifiable/Depends)
                - confidence_level: High/Medium/Low
                - confidence_explanation: Why this confidence level
                - apologetics_techniques: List of techniques identified
                - counterevidence: Any counterevidence found
                - verification_notes: Notes on source verification
                - raw_response: Full LLM response

        Raises:
            AgentExecutionError: If execution fails or output cannot be parsed
        """
        claim = input_data.get("claim_text", "")
        evidence_summary = input_data.get("evidence_summary", "")
        primary_sources = input_data.get("primary_sources", [])
        scholarly_sources = input_data.get("scholarly_sources", [])

        if not claim:
            raise AgentExecutionError("No claim provided to AdversarialCheckerAgent")

        # Construct user message
        user_message = f"""
Attempt to falsify this analysis:

Claim: {claim}
Evidence Summary: {evidence_summary}

Primary Sources: {json.dumps(primary_sources, indent=2)}
Scholarly Sources: {json.dumps(scholarly_sources, indent=2)}

Please respond with a JSON object containing:
{{
  "verdict": "One of: True, Misleading, False, Unfalsifiable, Depends on Definitions",
  "confidence_level": "High, Medium, or Low",
  "confidence_explanation": "Why this confidence level (2-3 sentences)",
  "apologetics_techniques": ["List of techniques used, if any"],
  "counterevidence": "Any counterevidence found (or 'None identified')",
  "verification_notes": "Notes on quote verification and source accuracy"
}}

Verdict categories:
- True: Claim is factually accurate
- Misleading: Contains truth but misrepresents context
- False: Claim is factually incorrect
- Unfalsifiable: Cannot be tested empirically
- Depends on Definitions: Depends on how terms are defined
"""

        try:
            # Call LLM
            response = await self.call_llm(user_message)
            raw_content = response["content"]

            # Parse JSON using shared utility function
            content = extract_json_from_response(raw_content)
            parsed = json.loads(content)

            # Validate required fields
            required_fields = [
                "verdict", "confidence_level", "confidence_explanation",
                "apologetics_techniques", "counterevidence", "verification_notes"
            ]
            for field in required_fields:
                if field not in parsed:
                    raise AgentExecutionError(
                        f"AdversarialCheckerAgent output missing required field: {field}"
                    )

            return {
                "verdict": parsed["verdict"],
                "confidence_level": parsed["confidence_level"],
                "confidence_explanation": parsed["confidence_explanation"],
                "apologetics_techniques": parsed["apologetics_techniques"],
                "counterevidence": parsed["counterevidence"],
                "verification_notes": parsed["verification_notes"],
                "raw_response": raw_content,
                "usage": response.get("usage", {}),
            }

        except json.JSONDecodeError as e:
            raise AgentExecutionError(
                f"AdversarialCheckerAgent failed to parse JSON output: {str(e)}"
            )
        except Exception as e:
            raise AgentExecutionError(
                f"AdversarialCheckerAgent execution failed: {str(e)}"
            )
