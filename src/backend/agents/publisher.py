"""
Publisher Agent for TheReceipts pipeline.

Fifth and final agent in the pipeline. Creates:
- Audit summary (what was checked, by whom)
- Known limitations (what was NOT checked)
- What evidence would change the verdict
- Category tags for UI navigation
"""

import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, AgentExecutionError, extract_json_from_response


class PublisherAgent(BaseAgent):
    """
    Agent that creates transparency documentation and finalizes the claim card.

    Takes all previous analysis and creates:
    - Agent audit summary
    - Known limitations
    - What would change the verdict
    - Category tags for navigation
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize PublisherAgent."""
        super().__init__(agent_name="publisher", db_session=db_session)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create audit summary and finalize claim card.

        Args:
            input_data: Dict containing all previous agent outputs

        Returns:
            Dict containing:
                - audit_summary: Summary of what was checked
                - limitations: What was NOT checked or known gaps
                - change_verdict_if: What evidence would change verdict
                - category_tags: List of category names for UI navigation
                - raw_response: Full LLM response

        Raises:
            AgentExecutionError: If execution fails or output cannot be parsed
        """
        claim = input_data.get("claim_text", "")
        claim_type = input_data.get("claim_type", "")
        verdict = input_data.get("verdict", "")

        if not claim:
            raise AgentExecutionError("No claim provided to PublisherAgent")

        # Construct user message with pipeline context
        pipeline_summary = {
            "claim": claim,
            "claim_type": claim_type,
            "claimant": input_data.get("claimant", ""),
            "verdict": verdict,
            "confidence_level": input_data.get("confidence_level", ""),
            "primary_sources_count": len(input_data.get("primary_sources", [])),
            "scholarly_sources_count": len(input_data.get("scholarly_sources", [])),
            "apologetics_techniques": input_data.get("apologetics_techniques", []),
        }

        user_message = f"""
Create the audit summary and category tags for this claim analysis:

Pipeline Summary:
{json.dumps(pipeline_summary, indent=2)}

Please respond with a JSON object containing:
{{
  "audit_summary": "Summary of what the 5-agent pipeline checked (2-3 sentences)",
  "limitations": "What was NOT checked or known gaps in analysis (2-3 bullet points as list)",
  "change_verdict_if": "What new evidence would change the verdict (1-2 sentences)",
  "category_tags": ["List of relevant category names for UI navigation"]
}}

Category options (select 1-3 most relevant):
- Genesis (creation, flood, early biblical history)
- Canon (biblical authorship, compilation, manuscript history)
- Doctrine (theology, church teachings, dogma)
- Ethics (morality, biblical commands, social issues)
- Institutions (church history, denominations, religious organizations)
- Historical Claims (non-biblical historical assertions)
- Scientific Claims (cosmology, biology, archaeology)
- Translation Issues (biblical translation debates)
"""

        try:
            # Call LLM
            response = await self.call_llm(user_message)
            raw_content = response["content"]

            # Parse JSON using shared utility function
            content = extract_json_from_response(raw_content)
            parsed = json.loads(content)

            # Validate required fields
            required_fields = ["audit_summary", "limitations", "change_verdict_if", "category_tags"]
            for field in required_fields:
                if field not in parsed:
                    raise AgentExecutionError(
                        f"PublisherAgent output missing required field: {field}"
                    )

            return {
                "audit_summary": parsed["audit_summary"],
                "limitations": parsed["limitations"],
                "change_verdict_if": parsed["change_verdict_if"],
                "category_tags": parsed["category_tags"],
                "raw_response": raw_content,
                "usage": response.get("usage", {}),
            }

        except json.JSONDecodeError as e:
            raise AgentExecutionError(
                f"PublisherAgent failed to parse JSON output: {str(e)}"
            )
        except Exception as e:
            raise AgentExecutionError(
                f"PublisherAgent execution failed: {str(e)}"
            )
